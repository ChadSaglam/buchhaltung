"""Booking CRUD endpoints with stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.booking import Booking
from app.models.user import User
from app.services.receipts import content_type_for_key, key_belongs_to_tenant, read_receipt

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class BookingCreate(BaseModel):
    datum: str = ""
    beschreibung: str = ""
    betrag: float = 0
    kt_soll: str = ""
    kt_haben: str = ""
    mwst_code: str = ""
    mwst_pct: str = ""
    mwst_amount: float = 0
    beleg: str = ""
    rechnung: str = ""
    source: str = ""
    # Key returned by /api/scanner/extract or /api/pdf/parse for the uploaded document.
    source_key: str | None = None


@router.get("/")
async def list_bookings(
    source: str | None = None,
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Booking).where(Booking.tenant_id == user.tenant_id)
    if source:
        query = query.where(Booking.source == source)
    query = query.order_by(Booking.id.desc()).limit(limit)
    result = await db.execute(query)
    bookings = result.scalars().all()
    return [
        {
            "id": b.id,
            "datum": b.datum,
            "beschreibung": b.beschreibung,
            "betrag": b.betrag,
            "kt_soll": b.kt_soll,
            "kt_haben": b.kt_haben,
            "mwst_code": b.mwst_code,
            "mwst_pct": b.mwst_pct,
            "mwst_amount": b.mwst_amount,
            "beleg": b.beleg,
            "rechnung": b.rechnung,
            "source": b.source,
            "source_key": b.source_key,
        }
        for b in bookings
    ]


@router.post("/")
async def create_bookings(
    body: BookingCreate | list[BookingCreate],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = body if isinstance(body, list) else [body]
    for item in items:
        # A key is only accepted when it addresses this tenant's own document.
        if item.source_key and not key_belongs_to_tenant(item.source_key, user.tenant_id):
            raise HTTPException(status_code=400, detail="Ungültiger Beleg-Schlüssel.")
    created = []
    for item in items:
        booking = Booking(
            tenant_id=user.tenant_id,
            datum=item.datum,
            beschreibung=item.beschreibung,
            betrag=item.betrag,
            kt_soll=item.kt_soll,
            kt_haben=item.kt_haben,
            mwst_code=item.mwst_code,
            mwst_pct=item.mwst_pct,
            mwst_amount=item.mwst_amount,
            beleg=item.beleg,
            rechnung=item.rechnung,
            source=item.source,
            source_key=item.source_key or None,
        )
        db.add(booking)
        created.append(booking)
    await db.flush()
    return [{"id": b.id, "status": "created"} for b in created]


@router.get("/stats")
async def booking_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total_result = await db.execute(
        select(func.count()).select_from(Booking).where(Booking.tenant_id == user.tenant_id)
    )
    total_count = total_result.scalar() or 0

    sum_result = await db.execute(select(func.sum(Booking.betrag)).where(Booking.tenant_id == user.tenant_id))
    total_amount = sum_result.scalar() or 0

    source_result = await db.execute(
        select(Booking.source, func.count()).where(Booking.tenant_id == user.tenant_id).group_by(Booking.source)
    )
    by_source = {row[0] or "unknown": row[1] for row in source_result.all()}

    return {
        "total_count": total_count,
        "total_amount": float(total_amount),
        "by_source": by_source,
    }


@router.get("/{booking_id}/source")
async def booking_source(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """The stored document (receipt image / statement PDF) a booking was created from."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id, Booking.tenant_id == user.tenant_id))
    booking = result.scalar_one_or_none()
    content = read_receipt(booking.source_key, user.tenant_id) if booking and booking.source_key else None
    if content is None:
        # Foreign, unknown, keyless or vanished document all look the same to the caller.
        raise HTTPException(status_code=404, detail="Kein Beleg zu dieser Buchung gefunden.")
    filename = booking.source_key.rsplit("/", 1)[-1]
    return Response(
        content=content,
        media_type=content_type_for_key(booking.source_key),
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
