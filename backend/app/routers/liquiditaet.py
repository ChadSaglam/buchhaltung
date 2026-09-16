"""Liquidität + Steuerrückstellung — /api/liquiditaet (B-71)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.liquiditaet import LiquiditaetResponse
from app.services.liquiditaet import LiquiditaetService

router = APIRouter(prefix="/api/liquiditaet", tags=["liquiditaet"])


@router.get("/", response_model=LiquiditaetResponse)
async def liquiditaet(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LiquiditaetResponse:
    """90-day cash view plus what to set aside for tax."""
    report = await LiquiditaetService(db, user).report()
    return LiquiditaetResponse.model_validate(report)
