"""Which tenant the current piece of work belongs to (B-24, ADR-002).

The application already filters every query by `tenant_id`. This is the value
that lets the *database* check the same thing, so a query the ORM never saw — a
raw ``text()``, a psql session, a future reporting job, a forgotten ``.where`` on
a new endpoint — cannot return another tenant's rows.

A ``ContextVar`` rather than a session attribute, because the value has to reach
a SQLAlchemy event handler that only gets the connection. It is per-task, so two
concurrent requests never see each other's tenant, and FastAPI's request handling
runs each request in its own task.

Fail closed is the whole point. When nothing set a tenant, the GUC is not set,
``current_setting('app.tenant_id', true)`` is NULL, and every RLS policy
evaluates ``NULL = tenant_id`` — never true. A forgotten context site shows up as
an empty list, which is the failure you want; the alternative is the one where it
shows up as somebody else's bookkeeping.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token

logger = logging.getLogger(__name__)

#: None = no tenant established. Not 0, and not "the first tenant" — see the
#: module docstring: a missing context has to be distinguishable from a real id.
_tenant_id: ContextVar[int | None] = ContextVar("app_tenant_id", default=None)


def set_tenant(tenant_id: int | None) -> Token:
    """Establish the tenant for this task. Returns a token for ``reset_tenant``."""
    return _tenant_id.set(int(tenant_id) if tenant_id is not None else None)


def reset_tenant(token: Token) -> None:
    _tenant_id.reset(token)


def current_tenant() -> int | None:
    return _tenant_id.get()


@contextmanager
def tenant_scope(tenant_id: int | None):
    """Run a block as one tenant, then put the previous value back.

    For the paths that have no request behind them — the training worker claiming
    a job, a platform event carrying its tenant in an HMAC-verified payload.
    """
    token = set_tenant(tenant_id)
    try:
        yield
    finally:
        reset_tenant(token)
