"""lohn_settings.freigegeben (B-72)

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-09-16

Rule 5 of docs/B-72-LOHN-SPEC.md. False for everyone, including tenants that
already have rates on file: the sign-off is a statement that one real month was
checked by a person, and no migration can make that statement on their behalf.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e0f1a2b3c4d5"
down_revision: str | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lohn_settings",
        sa.Column("freigegeben", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("lohn_settings", sa.Column("freigegeben_am", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("lohn_settings", "freigegeben_am")
    op.drop_column("lohn_settings", "freigegeben")
