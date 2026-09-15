"""bank_transactions + matches — Abgleich (brainstorm phase 3)

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-09-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("bank_transactions"):
        op.create_table(
            "bank_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="offen"),
            sa.Column("value_date", sa.Date(), nullable=True),
            sa.Column("booking_date", sa.Date(), nullable=True),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="CHF"),
            sa.Column("reference", sa.String(length=27), nullable=False, server_default=""),
            sa.Column("counterparty", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("statement_key", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("dedup_key", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("source", sa.String(length=20), nullable=False, server_default="pdf"),
            sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True),
            sa.Column("uploaded_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_bank_transactions_tenant_id", "bank_transactions", ["tenant_id"])
        op.create_index("ix_bank_transactions_tenant_status", "bank_transactions", ["tenant_id", "status"])
        op.create_index("ix_bank_transactions_tenant_amount", "bank_transactions", ["tenant_id", "amount"])
        op.create_index("uq_bank_transactions_dedup", "bank_transactions", ["tenant_id", "dedup_key"], unique=True)

    if not insp.has_table("matches"):
        op.create_table(
            "matches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "transaction_id",
                sa.Integer(),
                sa.ForeignKey("bank_transactions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="vorgeschlagen"),
            sa.Column("tier", sa.String(length=20), nullable=False, server_default="betrag_datum"),
            sa.Column("score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("decided_by", sa.Integer(), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_matches_tenant_id", "matches", ["tenant_id"])
        op.create_index("ix_matches_tenant_status", "matches", ["tenant_id", "status"])
        op.create_index("ix_matches_transaction", "matches", ["transaction_id"])
        op.create_index("ix_matches_document", "matches", ["document_id"])
        op.create_index("uq_matches_pair", "matches", ["tenant_id", "document_id", "transaction_id"], unique=True)


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("matches"):
        op.drop_table("matches")
    if insp.has_table("bank_transactions"):
        op.drop_table("bank_transactions")
