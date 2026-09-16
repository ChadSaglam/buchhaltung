"""company_profiles.gewinnsteuer_satz (B-71)

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-09-16

Nullable on purpose. The effective Swiss corporate income tax rate depends on
the canton *and* the commune, so there is no defensible default — without a
rate the Liquidität card shows the sourced range instead of a guess.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("company_profiles", sa.Column("gewinnsteuer_satz", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("company_profiles", "gewinnsteuer_satz")
