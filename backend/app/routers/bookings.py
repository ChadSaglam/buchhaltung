"""Booking CRUD endpoints with stats.

The bulk create accepts an ``Idempotency-Key`` header (B-52): a client that
retries after a timeout gets the *first* answer back instead of a second set of
bookings. The key is stored per tenant with a unique constraint, so two
parallel retries cannot both win.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_editor
from app.core.uploads import MAX_BULK_BOOKINGS, check_count
from app.models.booking import Booking
from app.models.idempotency_key import IdempotencyKey
from app.models.user import User
from app.schemas.booking import BookingStatsResponse
from app.schemas.common import Money
from app.services.audit_log import audit
from app.services.export import round_chf
from app.services.receipts import content_type_for_key, key_belongs_to_tenant, read_receipt

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class BookingCreate(BaseModel):
    datum: str = ""
    beschreibung: str = ""
    betrag: Money = 0
    kt_soll: str = ""
    kt_haben: str = ""
    mwst_code: str = ""
    mwst_pct: str = ""
    mwst_amount: Money = 0
    beleg: str = ""
    rechnung: str = ""
    source: str = ""
    # Key returned by /api/scanner/extract or /api/pdf/parse for the uploaded document.
    source_key: str | None = None


@router.get("/")
async def list_bookings(
    source: str | None = None,
    limit: int = Query(500, ge=1, le=1000),
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


ENDPOINT_BULK = "bookings.create"


async def _replay(db: AsyncSession, tenant_id: int, key: str) -> list | None:
    """The answer this key already produced, or None when it is the first time."""
    row = await db.scalar(
        select(IdempotencyKey.response).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.key == key,
            IdempotencyKey.endpoint == ENDPOINT_BULK,
        )
    )
    if row is None:
        return None
    try:
        return json.loads(row)
    except ValueError:  # pragma: no cover - only a hand-edited row gets here
        return None


@router.post("/")
async def create_bookings(
    body: BookingCreate | list[BookingCreate],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
):
    if idempotency_key:
        replayed = await _replay(db, user.tenant_id, idempotency_key)
        if replayed is not None:
            return replayed

    items = body if isinstance(body, list) else [body]
    # A bulk post is cheap to send and expensive to write (B-54).
    check_count(items, max_items=MAX_BULK_BOOKINGS, label="Buchungen")
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
    result = [{"id": b.id, "status": "created"} for b in created]
    await audit(
        db,
        user,
        "booking.create",
        target_type="booking",
        target_id=created[0].id if len(created) == 1 else None,
        anzahl=len(created),
        total=float(round_chf(sum(float(b.betrag or 0.0) for b in created))),
    )

    if idempotency_key:
        try:
            async with db.begin_nested():  # savepoint: a parallel retry must not kill the request
                db.add(
                    IdempotencyKey(
                        tenant_id=user.tenant_id,
                        key=idempotency_key,
                        endpoint=ENDPOINT_BULK,
                        response=json.dumps(result),
                    )
                )
                await db.flush()
        except IntegrityError:
            # Someone else stored the same key while we were writing: their
            # bookings are the ones that count, ours are rolled back with them.
            await db.rollback()
            replayed = await _replay(db, user.tenant_id, idempotency_key)
            if replayed is not None:
                return replayed
            raise HTTPException(409, "Dieser Idempotency-Key wird gerade verarbeitet.") from None
    return result


@router.get("/stats", response_model=BookingStatsResponse)
async def booking_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total_result = await db.execute(
        select(func.count()).select_from(Booking).where(Booking.tenant_id == user.tenant_id)
    )
    total_count = total_result.scalar() or 0

    # B-51: PostgreSQL sums the Numeric column exactly; round once, hand out a float.
    sum_result = await db.execute(select(func.sum(Booking.betrag)).where(Booking.tenant_id == user.tenant_id))
    total_amount = float(round_chf(sum_result.scalar() or 0))

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
