from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 10


async def dispatch_webhook(
    db: AsyncSession,
    tenant_id: int,
    event: str,
    payload: dict,
) -> None:
    """Fire-and-forget POST to tenant webhook_url if configured."""
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    webhook_url = getattr(tenant, "webhook_url", None)
    if not webhook_url:
        return

    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            await client.post(
                webhook_url,
                json={"event": event, "tenant_id": tenant_id, "data": payload},
                headers={"Content-Type": "application/json"},
            )
    except Exception as e:
        logger.warning(f"[WEBHOOK] tenant={tenant_id} event={event} failed: {e}")