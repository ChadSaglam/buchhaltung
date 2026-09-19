"""training_data.betrag — amount memory (Betrag-Gedächtnis)

Revision ID: d7e8f9a0b1c2
Revises: c1d2e3f4a5b6
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("training_data", "betrag"):
        op.add_column("training_data", sa.Column("betrag", sa.Float(), nullable=True))


def downgrade() -> None:
    if _has_column("training_data", "betrag"):
        op.drop_column("training_data", "betrag")
