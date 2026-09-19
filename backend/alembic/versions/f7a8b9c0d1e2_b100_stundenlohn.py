"""B-100: an employee is paid by the month or by the hour

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-18

Payroll knew one shape of employee: a fixed monthly gross, pro-rated by calendar
days when the month was partial. A person paid by the hour has no monthly gross
at all, and pro-rating one would be inventing a number.

Three columns:
- mitarbeiter.lohnart     — "monat" (the existing behaviour, and the default for
  every existing row) or "stunde"
- mitarbeiter.stundenlohn — gross per hour, compulsory when lohnart is "stunde"
- lohnabrechnungen.stunden / .stundenlohn — what a settled month was actually
  computed from, stored so it is never re-derived

Existing rows become "monat" with stundenlohn 0, which is exactly what they were.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def _chf() -> sa.types.TypeEngine:
    # models/types.py:Chf — Numeric on Postgres, Float on SQLite (B-51).
    return sa.Numeric(12, 2) if op.get_bind().dialect.name == "postgresql" else sa.Float()


def upgrade() -> None:
    with op.batch_alter_table("mitarbeiter") as b:
        b.add_column(sa.Column("lohnart", sa.String(10), nullable=False, server_default="monat"))
        b.add_column(sa.Column("stundenlohn", _chf(), nullable=False, server_default="0"))
    with op.batch_alter_table("lohnabrechnungen") as b:
        # Hours are not money: two decimals, but never a Chf column.
        b.add_column(sa.Column("stunden", sa.Float(), nullable=False, server_default="0"))
        b.add_column(sa.Column("stundenlohn", _chf(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("lohnabrechnungen") as b:
        b.drop_column("stundenlohn")
        b.drop_column("stunden")
    with op.batch_alter_table("mitarbeiter") as b:
        b.drop_column("stundenlohn")
        b.drop_column("lohnart")
