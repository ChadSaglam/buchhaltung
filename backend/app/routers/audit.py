from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.audit_log import AuditLogService

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _serialize(entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "action": entry.action,
        "actor_user_id": entry.actor_user_id,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "detail": entry.detail,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.get("/")
async def list_audit(
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    service = AuditLogService(user.tenant_id, db)
    entries = await service.list(limit=limit)
    return {"count": len(entries), "items": [_serialize(e) for e in entries]}