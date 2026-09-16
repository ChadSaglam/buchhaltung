from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin, require_editor
from app.core.rate_limit import heavy_limit, limiter
from app.core.uploads import MAX_RECEIPT_BYTES, read_upload
from app.models.user import User
from app.schemas.scanner import (
    ScannerConfigResponse,
    ScannerConfigUpdate,
    ScannerExtractResponse,
    ScannerStatusResponse,
)
from app.services.scanner.scanner_service import ScannerService

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


@router.get("/status", response_model=ScannerStatusResponse)
async def scanner_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScannerStatusResponse:
    service = ScannerService(db=db, user=user)
    return await service.get_status()


@router.get("/vision-status", response_model=ScannerStatusResponse)
async def vision_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScannerStatusResponse:
    service = ScannerService(db=db, user=user)
    return await service.get_status()


@router.get("/config", response_model=ScannerConfigResponse)
async def get_scanner_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScannerConfigResponse:
    service = ScannerService(db=db, user=user)
    return await service.get_config()


@router.put("/config", response_model=ScannerConfigResponse)
async def update_scanner_config(
    payload: ScannerConfigUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ScannerConfigResponse:
    service = ScannerService(db=db, user=user)
    return await service.update_config(payload)


@router.post("/extract", response_model=ScannerExtractResponse)
@limiter.limit(heavy_limit)
async def extract_invoice_endpoint(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form(default=""),
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> ScannerExtractResponse:
    service = ScannerService(db=db, user=user)
    content = await read_upload(file, max_bytes=MAX_RECEIPT_BYTES, label="Beleg")
    kwargs: dict[str, Any] = {
        "file_name": file.filename or "upload",
        "content_type": file.content_type or "",
        "content": content,
        "model": model,
    }
    # B-15: a client that accepts SSE gets every pipeline step as it happens; others get JSON.
    if "text/event-stream" in request.headers.get("accept", ""):
        return StreamingResponse(  # type: ignore[return-value]
            service.extract_events(**kwargs),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )
    return await service.extract(**kwargs)
