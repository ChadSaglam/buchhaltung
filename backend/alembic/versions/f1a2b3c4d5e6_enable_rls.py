"""Row-Level Security on the tenant-scoped tables (B-24)

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-09-16

ADR-002. The application already filters by tenant on every query; this is the
backstop for the query it never sees — a raw ``text()``, a psql session, a
reporting job, a forgotten ``.where`` on a new endpoint.

Three details that are the whole point:

* ``FORCE ROW LEVEL SECURITY``, not just ``ENABLE``. Postgres exempts the table
  *owner* from its own policies, and in a default compose deployment the app
  connects as the owner — which would leave RLS on, passing, and doing nothing.
* the policy compares against ``current_setting('app.tenant_id', true)``, which
  is NULL when nothing set it. ``NULL = tenant_id`` is never true, so a missing
  context reads as zero rows and writes are rejected. It fails closed.
* ``WITH CHECK`` as well as ``USING``: without it a session scoped to tenant 1
  could still INSERT a row carrying ``tenant_id = 2`` — invisible to itself, and
  perfectly visible to tenant 2.

SQLite has none of this. The migration is a no-op there and ``tests/test_rls.py``
skips without Postgres; CI's PG job is where this is actually proven.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.core.rls import POLICY_NAME, RLS_TABLES, TENANT_PREDICATE

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {POLICY_NAME} ON {table} USING ({TENANT_PREDICATE}) WITH CHECK ({TENANT_PREDICATE})")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
