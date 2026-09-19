"""Was der Mandant diesen Monat verbraucht hat (B-23).

Dieselbe Quelle wie die Durchsetzung — `PlanLimits` — damit die angezeigte
Zahl und die Zahl, die ablehnt, nicht auseinanderlaufen können.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.usage import UsageResponse
from app.services.plan_limits import PlanLimits

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
async def usage(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PlanLimits(user.tenant_id, db).snapshot()
