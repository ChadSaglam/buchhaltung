from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User


async def create_tenant(db: AsyncSession, name: str | None = None) -> Tenant:
    tenant = Tenant(name=name or f"tenant-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def create_user(
    db: AsyncSession,
    tenant: Tenant,
    email: str | None = None,
    password: str = "Test1234!",
) -> User:
    user = User(
        email=email or f"{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash(password),
        tenant_id=tenant.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
