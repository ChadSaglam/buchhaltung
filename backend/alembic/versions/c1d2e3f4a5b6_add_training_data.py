"""add training_data (B-39)

`TrainingRow` existed as a model but was never exported from `app.models`, so
Alembic (and the CI drift check) never saw it and no migration created the
table. Dev/test databases got it through `create_all`; a production database
(`AUTO_CREATE_TABLES=false`) did not, and Banana import, every training job and
`/api/classify/top-classes` failed with 500.

Idempotent on purpose: databases that already have the table from
`create_all` must upgrade cleanly.

Revision ID: c1d2e3f4a5b6
Revises: a400bdc46480
Create Date: 2026-09-13 18:40:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'a400bdc46480'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("training_data"):
        op.create_table(
            "training_data",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("beschreibung", sa.Text(), nullable=False),
            sa.Column("kt_soll", sa.String(length=20), nullable=False),
            sa.Column("kt_haben", sa.String(length=20), nullable=False),
            sa.Column("mwst_code", sa.String(length=10), nullable=False),
            sa.Column("mwst_pct", sa.String(length=10), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    existing = {ix["name"] for ix in inspector.get_indexes("training_data")} if inspector.has_table("training_data") else set()
    if "ix_training_data_tenant_id" not in existing:
        op.create_index("ix_training_data_tenant_id", "training_data", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_training_data_tenant_id", table_name="training_data")
    op.drop_table("training_data")
