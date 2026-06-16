from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_event import UsageEvent


class UsageMeter:
    def __init__(self, tenant_id: int, db: AsyncSession):
        self.tenant_id = tenant_id
        self.db = db

    async def record(self, event_type: str, quantity: int = 1) -> UsageEvent:
        event = UsageEvent(
            tenant_id=self.tenant_id,
            event_type=event_type,
            quantity=quantity,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def summary(self, since: datetime | None = None) -> dict[str, int]:
        stmt = (
            select(UsageEvent.event_type, func.sum(UsageEvent.quantity))
            .where(UsageEvent.tenant_id == self.tenant_id)
            .group_by(UsageEvent.event_type)
        )
        if since is not None:
            stmt = stmt.where(UsageEvent.created_at >= since)
        result = await self.db.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}