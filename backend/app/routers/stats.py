"""Extended stats endpoint for Lernverlauf charts."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.booking import Booking
from app.models.correction import Correction
from app.models.memory import Memory
from app.models.user import User
from app.schemas.stats import LearningStatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/learning", response_model=LearningStatsResponse)
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
    memory_distribution = [{"account": row[0] or "—", "count": row[1]} for row in mem_by_account.all()]

    # Corrections by corrected_soll (what accounts get corrected to)
    corr_by_account = await db.execute(
        select(Correction.corrected_soll, func.count())
        .where(Correction.tenant_id == tid)
        .group_by(Correction.corrected_soll)
        .order_by(func.count().desc())
        .limit(15)
    )
    correction_distribution = [{"account": row[0] or "—", "count": row[1]} for row in corr_by_account.all()]

    # Bookings by source
    bookings_by_source = await db.execute(
        select(Booking.source, func.count()).where(Booking.tenant_id == tid).group_by(Booking.source)
    )
    source_distribution = [{"source": row[0] or "unbekannt", "count": row[1]} for row in bookings_by_source.all()]

    # B-27: the booking total is the source histogram added up — it is grouped by
    # `source` with no LIMIT, so every booking is in exactly one bucket. Asking
    # the database for a number it just handed over was a third round trip.
    booking_count = sum(item["count"] for item in source_distribution)

    # The other two totals cannot be derived: their histograms are LIMIT 15.
    # One statement for both, though — two scalar subqueries, one round trip.
    mem_count, corr_count = (
        await db.execute(
            select(
                select(func.count()).select_from(Memory).where(Memory.tenant_id == tid).scalar_subquery(),
                select(func.count()).select_from(Correction).where(Correction.tenant_id == tid).scalar_subquery(),
            )
        )
    ).one()

    return {
        "memory_count": mem_count or 0,
        "correction_count": corr_count or 0,
        "booking_count": booking_count,
        "memory_distribution": memory_distribution,
        "correction_distribution": correction_distribution,
        "source_distribution": source_distribution,
    }
