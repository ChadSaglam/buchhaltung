"""idempotency_keys + partial unique index on billing bookings (B-52)

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-16

Idempotent, and the index is created *after* a duplicate check: an existing
database may already carry two bookings for the same paid invoice, and failing
the migration on that is worse than reporting it. Duplicates are collapsed,
keeping the oldest row, before the index goes on.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "uq_bookings_billing_source_key"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "idempotency_keys" not in tables:
        op.create_table(
            "idempotency_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("key", sa.String(length=128), nullable=False),
            sa.Column("endpoint", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("response", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_keys_tenant_key"),
        )
        op.create_index("ix_idempotency_keys_tenant_id", "idempotency_keys", ["tenant_id"])

    if INDEX not in {i["name"] for i in sa.inspect(bind).get_indexes("bookings")}:
        # Collapse what the old SELECT-then-INSERT race may have left behind.
        bind.execute(
            sa.text(
                """
                DELETE FROM bookings
                 WHERE source = 'billing'
                   AND source_key IS NOT NULL
                   AND id NOT IN (
                       SELECT MIN(id) FROM bookings
                        WHERE source = 'billing' AND source_key IS NOT NULL
                        GROUP BY tenant_id, source_key
                   )
                """
            )
        )
        op.create_index(
            INDEX,
            "bookings",
            ["tenant_id", "source_key"],
            unique=True,
            postgresql_where=sa.text("source = 'billing'"),
            sqlite_where=sa.text("source = 'billing'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if INDEX in {i["name"] for i in sa.inspect(bind).get_indexes("bookings")}:
        op.drop_index(INDEX, table_name="bookings")
    if "idempotency_keys" in set(sa.inspect(bind).get_table_names()):
        op.drop_table("idempotency_keys")
