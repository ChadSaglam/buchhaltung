"""money columns Float → Numeric(12, 2) (B-51)

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-09-16

PostgreSQL only in effect: SQLite has no native decimal, keeps REAL, and is
dev/test anyway. Existing values are rounded half-up while they are cast, so a
0.1+0.2 artefact already in the table becomes the franc amount it was meant to
be instead of travelling on.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    ("bookings", "betrag"),
    ("bookings", "mwst_amount"),
    ("review_queue_items", "betrag"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(sa.inspect(bind).get_table_names())
    for table, column in COLUMNS:
        if table not in tables:
            continue
        op.alter_column(
            table,
            column,
            type_=sa.Numeric(12, 2),
            existing_type=sa.Float(),
            postgresql_using=f"ROUND({column}::numeric, 2)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(sa.inspect(bind).get_table_names())
    for table, column in COLUMNS:
        if table in tables:
            op.alter_column(table, column, type_=sa.Float(), existing_type=sa.Numeric(12, 2))
