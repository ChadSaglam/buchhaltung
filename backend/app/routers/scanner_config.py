"""Scanner-config endpoints — tenant-scoped read/update."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.scanner_config import ScannerConfigResponse, ScannerConfigUpdate
from app.services.scanner_config import ScannerConfigService

router = APIRouter(prefix="/api/scanner", tags=["scanner-config"])


@router.get("/config", response_model=ScannerConfigResponse)
async def get_scanner_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerConfigResponse:
    config = await ScannerConfigService(user.tenant_id, db).get_or_create()
    await db.commit()
    return ScannerConfigResponse.model_validate(config, from_attributes=True)


@router.patch("/config", response_model=ScannerConfigResponse)
async def update_scanner_config(
    body: ScannerConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScannerConfigResponse:
    config = await ScannerConfigService(user.tenant_id, db).update(
        body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ScannerConfigResponse.model_validate(config, from_attributes=True)