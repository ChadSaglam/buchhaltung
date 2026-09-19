"""documents — Rechnung/Beleg entity (brainstorm phase 1)

Revision ID: f0a1b2c3d4e5
Revises: e8f9a0b1c2d3
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("documents"):
        return
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="rechnung"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="offen"),
        sa.Column("file_key", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("vendor", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="CHF"),
        sa.Column("invoice_no", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("qr_iban", sa.String(length=34), nullable=False, server_default=""),
        sa.Column("qr_reference", sa.String(length=27), nullable=False, server_default=""),
        sa.Column("qr_message", sa.String(length=140), nullable=False, server_default=""),
        sa.Column("extraction_source", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("extraction_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("raw_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("kt_soll", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("kt_haben", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("mwst_code", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("mwst_pct", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("classification_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_tenant_status", "documents", ["tenant_id", "status"])
    op.create_index("ix_documents_tenant_reference", "documents", ["tenant_id", "qr_reference"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("documents"):
        op.drop_table("documents")
