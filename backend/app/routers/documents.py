"""Documents — bulk upload, list, correct (brainstorm phase 1)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_editor
from app.core.rate_limit import heavy_limit, limiter
from app.core.uploads import MAX_RECEIPT_BYTES, read_upload
from app.models.document import (
    DOCUMENT_STATUSES,
    STATUS_BEZAHLT,
    STATUS_EXPORTIERT,
    STATUS_FEHLER,
    STATUS_OFFEN,
    Document,
)
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentOut,
    DocumentSummary,
    DocumentUpdate,
    DocumentUploadResponse,
    DocumentUploadResult,
)
from app.services.audit_log import audit
from app.services.documents import DocumentService
from app.services.receipts import content_type_for_key, read_receipt

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_FILES_PER_UPLOAD = 50


@router.post("/", response_model=DocumentUploadResponse)
@limiter.limit(heavy_limit)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> DocumentUploadResponse:
    """Drag 1..50 invoices in; every file becomes a Document, failures included (status 'fehler')."""
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(400, f"Maximal {MAX_FILES_PER_UPLOAD} Dateien pro Upload.")
    service = DocumentService(db, user)
    results: list[DocumentUploadResult] = []
    for upload in files:
        name = upload.filename or "upload"
        try:
            content = await read_upload(upload, max_bytes=MAX_RECEIPT_BYTES, label=name)
            doc = await service.ingest(filename=name, content_type=upload.content_type or "", content=content)
            results.append(
                DocumentUploadResult(
                    filename=name,
                    ok=doc.status != STATUS_FEHLER,
                    document=DocumentOut.model_validate(doc),
                    error=doc.error or None,
                )
            )
        except HTTPException as exc:  # e.g. wrong file type — the other files still go through
            results.append(DocumentUploadResult(filename=name, ok=False, error=str(exc.detail)))
    await db.commit()
    for r in results:
        if r.document is not None:
            r.document = DocumentOut.model_validate(await db.get(Document, r.document.id))
    return DocumentUploadResponse(
        results=results, created=sum(r.ok for r in results), failed=sum(not r.ok for r in results)
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    status: str | None = Query(default=None),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentListResponse:
    stmt = select(Document).where(Document.tenant_id == user.tenant_id)
    if status:
        if status not in DOCUMENT_STATUSES:
            raise HTTPException(400, f"Unbekannter Status: {status}")
        stmt = stmt.where(Document.status == status)
    rows = (await db.execute(stmt.order_by(Document.id.desc()).limit(limit))).scalars().all()
    return DocumentListResponse(items=[DocumentOut.model_validate(r) for r in rows], count=len(rows))


@router.get("/summary", response_model=DocumentSummary)
async def documents_summary(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    counts = dict(
        (
            await db.execute(
                select(Document.status, func.count(Document.id))
                .where(Document.tenant_id == user.tenant_id)
                .group_by(Document.status)
            )
        ).all()
    )
    open_sum = (
        await db.execute(
            select(func.coalesce(func.sum(Document.amount), 0.0)).where(
                Document.tenant_id == user.tenant_id, Document.status == STATUS_OFFEN
            )
        )
    ).scalar() or 0.0
    overdue = (
        await db.execute(
            select(func.count(Document.id)).where(
                Document.tenant_id == user.tenant_id, Document.status == STATUS_OFFEN, Document.due_date < date.today()
            )
        )
    ).scalar() or 0
    return DocumentSummary(
        offen=counts.get(STATUS_OFFEN, 0),
        offen_betrag=round(float(open_sum), 2),
        ueberfaellig=overdue,
        bezahlt=counts.get(STATUS_BEZAHLT, 0),
        exportiert=counts.get(STATUS_EXPORTIERT, 0),
        fehler=counts.get(STATUS_FEHLER, 0),
    )


async def _own_document(db: AsyncSession, user: User, document_id: int) -> Document:
    doc = (
        await db.execute(select(Document).where(Document.id == document_id, Document.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Dokument nicht gefunden.")
    return doc


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return DocumentOut.model_validate(await _own_document(db, user, document_id))


@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: int,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
):
    doc = await _own_document(db, user, document_id)
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes and doc.status == STATUS_EXPORTIERT and changes["status"] != STATUS_EXPORTIERT:
        raise HTTPException(409, "Ein exportiertes Dokument kann nicht zurückgesetzt werden.")
    for field, value in changes.items():
        setattr(doc, field, value)
    if changes and doc.status == STATUS_FEHLER and "status" not in changes:
        doc.status, doc.error = STATUS_OFFEN, ""  # a manual correction makes a failed row usable
    if "status" in changes:
        # Only the status: offen ↔ bezahlt is an assertion about money, the rest
        # is correcting what was read off the page and the row itself is the record.
        await audit(
            db,
            user,
            "document.status",
            target_type="document",
            target_id=document_id,
            status=doc.status,
            betrag=float(doc.amount or 0.0),
        )
    await db.commit()
    await db.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.get("/{document_id}/file")
async def document_file(document_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    doc = await _own_document(db, user, document_id)
    content = read_receipt(doc.file_key, user.tenant_id)
    if content is None:
        raise HTTPException(404, "Datei nicht mehr vorhanden.")
    return Response(
        content=content,
        media_type=content_type_for_key(doc.file_key),
        headers={"Content-Disposition": f'inline; filename="{doc.filename or doc.file_key.rsplit("/", 1)[-1]}"'},
    )
