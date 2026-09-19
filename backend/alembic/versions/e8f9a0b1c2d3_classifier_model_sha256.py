"""classifier_models.model_sha256 — blob fingerprint (B-34)

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("classifier_models", "model_sha256"):
        op.add_column("classifier_models", sa.Column("model_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    if _has_column("classifier_models", "model_sha256"):
        op.drop_column("classifier_models", "model_sha256")
