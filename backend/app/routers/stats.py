"""Extended stats endpoint for Lernverlauf charts."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.memory import Memory
from app.models.correction import Correction
from app.models.booking import Booking

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/learning")
async def learning_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregated stats for Lernverlauf charts."""
    tid = user.tenant_id

    # Memory by KtSoll (top accounts in memory)
    mem_by_account = await db.execute(
        select(Memory.kt_soll, func.count())
        .where(Memory.tenant_id == tid)
        .group_by(Memory.kt_soll)
        .order_by(func.count().desc())
        .limit(15)
    )
    memory_distribution = [
        {"account": row[0], "count": row[1]} for row in mem_by_account.all()
    ]

    # Corrections by corrected_soll (what accounts get corrected to)
    corr_by_account = await db.execute(
        select(Correction.corrected_soll, func.count())
        .where(Correction.tenant_id == tid)
        .group_by(Correction.corrected_soll)
        .order_by(func.count().desc())
        .limit(15)
    )
    correction_distribution = [
        {"account": row[0], "count": row[1]} for row in corr_by_account.all()
    ]

    # Bookings by source
    bookings_by_source = await db.execute(
        select(Booking.source, func.count())
        .where(Booking.tenant_id == tid)
        .group_by(Booking.source)
    )
    source_distribution = [
        {"source": row[0] or "unbekannt", "count": row[1]}
        for row in bookings_by_source.all()
    ]

    # Totals
    mem_count = (await db.execute(
        select(func.count()).select_from(Memory).where(Memory.tenant_id == tid)
    )).scalar() or 0

    corr_count = (await db.execute(
        select(func.count()).select_from(Correction).where(Correction.tenant_id == tid)
    )).scalar() or 0

    booking_count = (await db.execute(
        select(func.count()).select_from(Booking).where(Booking.tenant_id == tid)
    )).scalar() or 0

    return {
        "memory_count": mem_count,
        "correction_count": corr_count,
        "booking_count": booking_count,
        "memory_distribution": memory_distribution,
        "correction_distribution": correction_distribution,
        "source_distribution": source_distribution,
    }
