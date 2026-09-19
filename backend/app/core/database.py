"""Engine, session factory, and the per-transaction tenant GUC (B-24).

The ``after_begin`` listener is the mechanism ADR-002 chose, and the reason is
the 27 places in this app that commit or roll back mid-request. A session-level
``SET`` would be lost after the first of them and, worse, would survive on the
pooled connection into the *next* request — a leak in the exact direction this is
meant to prevent. ``SET LOCAL`` re-issued at the start of every transaction is
the only variant that is correct with both, and it is also the only one that
works behind a transaction-mode pgbouncer.

SQLite has no RLS and no ``set_config``, so the listener is a no-op there. The
dev and unit suites therefore cannot prove any of this; ``test_rls.py`` runs
against Postgres and is skipped without it.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.tenant_context import current_tenant

logger = logging.getLogger(__name__)

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {"echo": False}
if not _is_sqlite:
    _engine_kwargs.update(pool_size=20, max_overflow=10)

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session = async_sessionmaker(engine, expire_on_commit=False)

#: `set_config(..., is_local => true)` is `SET LOCAL` with a bind parameter.
#: `SET LOCAL app.tenant_id = :x` is not parameterisable, and building that
#: statement by hand is how a cast turns into an injection point.
_SET_TENANT = text("SELECT set_config('app.tenant_id', :tenant_id, true)")


@event.listens_for(Session, "after_begin")
def _apply_tenant_guc(session: Session, transaction, connection) -> None:
    """Tell Postgres whose transaction this is, on every single transaction."""
    if connection.dialect.name != "postgresql":
        return
    tenant_id = current_tenant()
    if tenant_id is None:
        # Not an error: registration, login and the health probe all run before
        # any tenant exists. Logged at debug because on a busy server the
        # interesting version of this is the RLS-empty-result, not the line.
        logger.debug("[rls] transaction began with no tenant context; policies will match nothing")
        return
    connection.execute(_SET_TENANT, {"tenant_id": str(tenant_id)})


async def bind_tenant(session: AsyncSession, tenant_id: int) -> None:
    """Set the GUC on the transaction that is already open.

    ``get_current_user`` reads `users` and `tenants` before it knows the tenant,
    which starts the request's first transaction — so by the time the context
    exists, ``after_begin`` has already fired for it. Without this the first
    transaction of every request would run unscoped, which is precisely the one
    that goes on to do the request's work.

    Later transactions in the same request are covered by the listener.
    """
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    await session.execute(_SET_TENANT, {"tenant_id": str(int(tenant_id))})


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
