"""documents: direction (Debitor/Kreditor) + Mahnung state (B-65 Offene Posten)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-15

Idempotent: dev databases created with ``create_all`` already carry the columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    ("direction", sa.Column("direction", sa.String(length=10), nullable=False, server_default="eingang")),
    ("contact_email", sa.Column("contact_email", sa.String(length=255), nullable=False, server_default="")),
    ("mahnstufe", sa.Column("mahnstufe", sa.Integer(), nullable=False, server_default="0")),
    ("mahnung_sent_at", sa.Column("mahnung_sent_at", sa.DateTime(timezone=True), nullable=True)),
)
INDEX = "ix_documents_tenant_direction_status"


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = {c["name"] for c in insp.get_columns("documents")}
    with op.batch_alter_table("documents") as batch:
        for name, column in COLUMNS:
            if name not in existing:
                batch.add_column(column)
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("documents")}
    if INDEX not in indexes:
        op.create_index(INDEX, "documents", ["tenant_id", "direction", "status"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if INDEX in {i["name"] for i in insp.get_indexes("documents")}:
        op.drop_index(INDEX, table_name="documents")
    existing = {c["name"] for c in insp.get_columns("documents")}
    with op.batch_alter_table("documents") as batch:
        for name, _column in reversed(COLUMNS):
            if name in existing:
                batch.drop_column(name)
