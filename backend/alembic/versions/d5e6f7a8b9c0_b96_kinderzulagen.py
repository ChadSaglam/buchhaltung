"""B-96: Kinderzulagen are paid with the salary and are not massgebender Lohn

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-18

Found on the first real run: the payslip the owner brought shows Bruttolohn
6'657.95 (6'257.95 salary + 400 Kinderzulagen) with every deduction taken on
6'257.95. Our engine took them on 6'657.95. Familienzulagen are not part of
the massgebender Lohn (AHVV Art. 6) — they are paid out and taxed, but no
social-insurance rate applies to them.

Three columns:
- mitarbeiter.kinderzulagen_monat  — the recurring monthly amount (the
  Ausgleichskasse's decision names an amount, not a per-child formula)
- lohnabrechnungen.kinderzulagen   — what that month actually paid
- lohnabrechnungen.ahv_lohn        — the contributory base every rate was
  applied to, stored so a settled month is never re-derived

Existing rows: `ahv_lohn` is back-filled from `brutto`. Before this change
every Zulage was treated as AHV-pflichtig, so for a settled month the two
numbers were identical — that is what the back-fill preserves.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def _chf() -> sa.types.TypeEngine:
    # Same shape as models/types.py:Chf — Numeric on Postgres, Float on SQLite,
    # which has no decimal type (B-51).
    return sa.Numeric(12, 2) if op.get_bind().dialect.name == "postgresql" else sa.Float()


def upgrade() -> None:
    with op.batch_alter_table("mitarbeiter") as b:
        b.add_column(sa.Column("kinderzulagen_monat", _chf(), nullable=False, server_default="0"))
    with op.batch_alter_table("lohnabrechnungen") as b:
        b.add_column(sa.Column("kinderzulagen", _chf(), nullable=False, server_default="0"))
        b.add_column(sa.Column("ahv_lohn", _chf(), nullable=False, server_default="0"))
    # Every existing payslip was computed with brutto == massgebender Lohn.
    op.execute("UPDATE lohnabrechnungen SET ahv_lohn = brutto")


def downgrade() -> None:
    with op.batch_alter_table("lohnabrechnungen") as b:
        b.drop_column("ahv_lohn")
        b.drop_column("kinderzulagen")
    with op.batch_alter_table("mitarbeiter") as b:
        b.drop_column("kinderzulagen_monat")
