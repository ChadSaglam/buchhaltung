"""Banana batch export — /api/export/batches (brainstorm phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_editor
from app.core.rate_limit import heavy_limit, limiter
from app.models.user import User
from app.schemas.export_batch import (
    CreateBatchRequest,
    ExportBatchListResponse,
    ExportBatchOut,
    ExportCheck,
    PreflightResponse,
)
from app.services.audit_log import audit
from app.services.export_batch import ExportBatchService
from app.services.treuhand_pack import PackTooLarge, TreuhandPackService

router = APIRouter(prefix="/api/export/batches", tags=["export"])


def _attachment(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/preflight", response_model=PreflightResponse)
async def preflight(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PreflightResponse:
    """Is everything OK to export? One red/green list, nothing to configure."""
    pre = await ExportBatchService(db, user).preflight()
    return PreflightResponse(
        exportable=pre.exportable,
        total=pre.total,
        period_from=pre.period_from,
        period_to=pre.period_to,
        ready=pre.ready,
        blockers=pre.blockers,
        checks=[ExportCheck(**vars(c)) for c in pre.checks],
    )


@router.get("/", response_model=ExportBatchListResponse)
async def list_batches(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExportBatchListResponse:
    batches = await ExportBatchService(db, user).batches(limit=limit)
    return ExportBatchListResponse(items=[ExportBatchOut.model_validate(b) for b in batches], count=len(batches))


@router.post("/", response_model=ExportBatchOut)
@limiter.limit(heavy_limit)
async def create_batch(
    request: Request,
    body: CreateBatchRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> ExportBatchOut:
    """Hand everything reconciled over to Banana — once."""
    service = ExportBatchService(db, user)
    batch = await service.create(note=(body.note if body else ""))
    await audit(
        db,
        user,
        "export.batch",
        target_type="export_batch",
        target_id=batch.id,
        buchungen=batch.booking_count,
        total=float(batch.total_betrag or 0.0),
        pruefsumme=batch.checksum,
    )
    await db.commit()
    return ExportBatchOut.model_validate(batch)


@router.get("/{batch_id}", response_model=ExportBatchOut)
async def get_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExportBatchOut:
    return ExportBatchOut.model_validate(await ExportBatchService(db, user).batch(batch_id))


@router.get("/{batch_id}/file")
async def download_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """The same bytes every time — a re-download is not a second hand-off."""
    batch, content = await ExportBatchService(db, user).content(batch_id)
    return _attachment(content, batch.filename or f"banana_{batch_id}.txt")


@router.get("/{batch_id}/cover")
async def download_cover(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    batch, content = await ExportBatchService(db, user).cover_sheet(batch_id)
    return _attachment(content, f"deckblatt_{batch.id}.txt")


@router.get("/{batch_id}/pack.zip")
async def download_pack(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """The whole hand-off in one file (B-17).

    Cover sheet, the Banana import byte-identical to the batch, the receipts
    numbered to match the bookings, the same rows as a readable CSV, and the
    audit trail for the period. Building it is a read — nothing is stamped,
    nothing is marked as sent — so a Treuhänder who loses the e-mail gets the
    same zip again.
    """
    try:
        name, content = await TreuhandPackService(db, user).build(batch_id)
    except PackTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc
    await db.commit()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
