"""the five money columns B-51 missed: Float → Numeric(12, 2)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-09-16

B-51 converted `bookings` and `review_queue_items` and stopped there. These five
are the same kind of number and were left on `Float`:

* ``bank_transactions.amount`` — the bank movement itself;
* ``documents.amount`` — the invoice total read off the receipt, which drives
  Offene Posten and every Mahnung;
* ``export_batches.total_betrag`` / ``total_mwst`` — the figures printed on the
  cover sheet that goes to the Treuhänder, next to a checksum;
* ``matches.amount`` — the matched amount.

Same reasoning as B-51: 0.1 + 0.2 + 0.3 stored as binary floats sums to
0.6000000000000001, so every total reported from them was a rounded lie. Values
already in the table are rounded half-up as they are cast, so an artefact that is
already there becomes the franc amount it was meant to be instead of travelling on.

PostgreSQL only in effect — SQLite has no native decimal and is dev/test anyway,
which is exactly why this went unnoticed for a day.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    ("bank_transactions", "amount"),
    ("documents", "amount"),
    ("export_batches", "total_betrag"),
    ("export_batches", "total_mwst"),
    ("matches", "amount"),
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
