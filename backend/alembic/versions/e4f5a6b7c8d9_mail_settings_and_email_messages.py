"""mail_settings + email_messages — Belege per E-Mail (B-69)

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-16

Idempotent: dev databases created with ``create_all`` already carry both tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "mail_settings" not in tables:
        op.create_table(
            "mail_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("allow_list", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tenant_id", name="uq_mail_settings_tenant_id"),
        )
        op.create_index("ix_mail_settings_tenant_id", "mail_settings", ["tenant_id"])

    if "email_messages" not in tables:
        op.create_table(
            "email_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("message_id", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("from_addr", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("to_addr", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("subject", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="verarbeitet"),
            sa.Column("reason", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("document_ids", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tenant_id", "message_id", name="uq_email_messages_tenant_message"),
        )
        op.create_index("ix_email_messages_tenant_id", "email_messages", ["tenant_id"])
        op.create_index("ix_email_messages_tenant_created", "email_messages", ["tenant_id", "created_at"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "email_messages" in tables:
        op.drop_table("email_messages")
    if "mail_settings" in tables:
        op.drop_table("mail_settings")
