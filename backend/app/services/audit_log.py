"""Audit-log service — tenant-scoped append-only writes and reads."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


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
            select(AuditLog).where(AuditLog.tenant_id == self.tenant_id).order_by(AuditLog.id.desc()).limit(limit)
        )
        return list(result.scalars().all())


async def audit(
    db: AsyncSession,
    user: User,
    action: str,
    *,
    target_type: str = "",
    target_id: str | int | None = None,
    **detail,
) -> AuditLog:
    """One line at a call site (B-22).

    The three-line `AuditLogService(...).record(...)` is why most endpoints never
    grew one. `action` must be a key of `core.audit_actions.AUDIT_ACTIONS`; the
    completeness test drives every one of them through the API, so a typo here
    fails the suite instead of writing a row nobody will ever query for.
    """
    from app.core.audit_actions import AUDIT_ACTIONS

    assert action in AUDIT_ACTIONS, f"undeclared audit action {action!r} — add it to AUDIT_ACTIONS"
    return await AuditLogService(user.tenant_id, db).record(
        action=action,
        actor_user_id=user.id,
        target_type=target_type or None,
        target_id=target_id,
        detail=detail or None,
    )
