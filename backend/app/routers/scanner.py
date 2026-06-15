from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScannerConfigResponse:
    service = ScannerService(db=db, user=user)
    return await service.update_config(payload)


@router.post("/extract", response_model=ScannerExtractResponse)
async def extract_invoice_endpoint(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScannerExtractResponse:
    service = ScannerService(db=db, user=user)
    content = await file.read()
    return await service.extract(
        file_name=file.filename or "upload",
        content_type=file.content_type or "",
        content=content,
        model=model,
    )