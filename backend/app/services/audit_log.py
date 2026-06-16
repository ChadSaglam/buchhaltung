"""Audit-log service — tenant-scoped append-only writes and reads."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogService:
    def __init__(self, tenant_id: int, db: AsyncSession):
        self.tenant_id = tenant_id
        self.db = db

    async def record(
        self,
        action: str,
        actor_user_id: int | None = None,
        target_type: str | None = None,
        target_id: str | int | None = None,
        detail: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            tenant_id=self.tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list(self, limit: int = 200) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == self.tenant_id)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())