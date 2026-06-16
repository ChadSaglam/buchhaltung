from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.review_queue import ReviewQueueService
from app.services.audit_log import AuditLogService

router = APIRouter(prefix="/api/review", tags=["review"])


class ApproveRequest(BaseModel):
    corrected_soll: str | None = None
    corrected_haben: str | None = None
    corrected_mwst_code: str | None = None
    corrected_mwst_pct: str | None = None


def _serialize(item) -> dict[str, Any]:
    return {
        "id": item.id,
        "beschreibung": item.beschreibung,
        "betrag": item.betrag,
        "predicted_soll": item.predicted_soll,
        "predicted_haben": item.predicted_haben,
        "predicted_mwst_code": item.predicted_mwst_code,
        "predicted_mwst_pct": item.predicted_mwst_pct,
        "confidence": item.confidence,
        "source": item.source,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/")
async def list_pending(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    service = ReviewQueueService(user.tenant_id, db)
    items = await service.list_pending()
    threshold = await service.get_threshold()
    return {"threshold": threshold, "count": len(items), "items": [_serialize(i) for i in items]}


@router.post("/{item_id}/approve")
async def approve_item(
    item_id: int,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    service = ReviewQueueService(user.tenant_id, db)
    item = await service.approve(
        item_id,
        corrected_soll=body.corrected_soll,
        corrected_haben=body.corrected_haben,
        corrected_mwst_code=body.corrected_mwst_code,
        corrected_mwst_pct=body.corrected_mwst_pct,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden oder bereits bearbeitet.")

    await AuditLogService(user.tenant_id, db).record(
        action="review.approve",
        actor_user_id=user.id,
        target_type="review_queue_item",
        target_id=item_id,
        detail={"resolved_soll": item.resolved_soll, "resolved_haben": item.resolved_haben},
    )

    await db.commit()
    return {"status": "approved"}


@router.post("/{item_id}/reject")
async def reject_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    service = ReviewQueueService(user.tenant_id, db)
    item = await service.reject(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden oder bereits bearbeitet.")

    await AuditLogService(user.tenant_id, db).record(
        action="review.reject",
        actor_user_id=user.id,
        target_type="review_queue_item",
        target_id=item_id,
    )

    await db.commit()
    return {"status": "rejected"}