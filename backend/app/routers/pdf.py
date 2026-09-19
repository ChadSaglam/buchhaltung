"""PDF upload & parse endpoint."""

from __future__ import annotations

import asyncio
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_editor
from app.core.rate_limit import heavy_limit, limiter
from app.core.uploads import MAX_PDF_BYTES, read_upload
from app.models.user import User
from app.services.pdf_parser import extract_transactions_from_pdf
from app.services.receipts import store_receipt
from app.services.storage_quota import StorageQuota

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


@router.post("/parse")
@limiter.limit(heavy_limit)
async def parse_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Nur PDF-Dateien erlaubt.")

    content = await read_upload(file, max_bytes=MAX_PDF_BYTES, label="PDF")
    # The audit copy below is kept whether or not the parse works, so the quota
    # is checked before it is written, not after the disk is full (B-54).
    quota = StorageQuota(user.tenant_id, db)
    await quota.ensure_room_for(len(content))

    # Audit copy first (B-09): the statement survives even if parsing fails.
    source_key = await asyncio.to_thread(
        store_receipt,
        user.tenant_id,
        filename=file.filename,
        content_type=file.content_type or "application/pdf",
        content=content,
    )
    await quota.record(len(content))
    await db.commit()

    try:
        # pdfplumber is CPU-bound and takes seconds on a long statement (B-49).
        transactions = await asyncio.to_thread(extract_transactions_from_pdf, io.BytesIO(content))
    except Exception as e:
        raise HTTPException(422, f"PDF konnte nicht gelesen werden: {e}") from e

    if not transactions:
        raise HTTPException(422, "Keine Transaktionen gefunden.")

    return {"transactions": transactions, "count": len(transactions), "source_key": source_key}
