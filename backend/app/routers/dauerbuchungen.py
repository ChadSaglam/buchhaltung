"""Dauerbuchungen — /api/dauerbuchungen (B-74)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.dauerbuchungen import DauerbuchungenResponse, DauerbuchungOut
from app.services.dauerbuchungen import chf, erkennen, fehlende, monatsschluessel, summe_offen
from app.services.offene_posten import today_utc

router = APIRouter(prefix="/api/dauerbuchungen", tags=["dauerbuchungen"])


@router.get("/", response_model=DauerbuchungenResponse)
async def dauerbuchungen(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DauerbuchungenResponse:
    """What goes out every month, and which of it has not gone out yet."""
    heute = today_utc()
    rows = await db.execute(select(Booking).where(Booking.tenant_id == user.tenant_id))
    eintraege = erkennen(list(rows.scalars().all()), heute)

    return DauerbuchungenResponse(
        stichtag=heute,
        monat=monatsschluessel(heute),
        eintraege=[DauerbuchungOut.model_validate(e) for e in eintraege],
        fehlen=[DauerbuchungOut.model_validate(e) for e in fehlende(eintraege)],
        offen_total=summe_offen(eintraege),
        monatstotal=chf(sum(e.betrag for e in eintraege)),
    )
