"""usage_events.quantity → BIGINT (B-54)

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-16

B-54 started counting storage in *bytes* in this column. int32 stops at 2.1 GB,
so a tenant with more stored evidence than that — or a quota expressed in bytes,
which is what caught it — fails with `value out of int32 range`.

SQLite has no fixed-width integers, so the whole thing passed locally and only
surfaced on the Postgres CI job. Widening is safe in both directions for values
that already fit, which is every value there is today.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "usage_events",
        "quantity",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # Narrowing can fail on a row that no longer fits; that is the point of the
    # upgrade, so the downgrade is honest about it rather than truncating.
    op.alter_column(
        "usage_events",
        "quantity",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
