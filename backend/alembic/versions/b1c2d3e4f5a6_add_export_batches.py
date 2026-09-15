"""add export_batches + bookings.export_batch_id/exported_at (phase 4 Banana batch)

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-15

Idempotent: dev databases created with ``create_all`` already carry the table
and the columns, so every step checks the live schema first.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _inspector()
    tables = set(insp.get_table_names())

    if "export_batches" not in tables:
        op.create_table(
            "export_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("format", sa.String(length=20), nullable=False, server_default="banana"),
            sa.Column("filename", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("booking_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_betrag", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_mwst", sa.Float(), nullable=False, server_default="0"),
            sa.Column("period_from", sa.Date(), nullable=True),
            sa.Column("period_to", sa.Date(), nullable=True),
            sa.Column("checksum", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("note", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_export_batches_tenant_id", "export_batches", ["tenant_id"])
        op.create_index("ix_export_batches_tenant_created", "export_batches", ["tenant_id", "created_at"])

    booking_columns = {c["name"] for c in insp.get_columns("bookings")}
    with op.batch_alter_table("bookings") as batch:
        if "export_batch_id" not in booking_columns:
            batch.add_column(sa.Column("export_batch_id", sa.Integer(), nullable=True))
        if "exported_at" not in booking_columns:
            batch.add_column(sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True))

    insp = _inspector()
    indexes = {i["name"] for i in insp.get_indexes("bookings")}
    if "ix_bookings_export_batch_id" not in indexes:
        op.create_index("ix_bookings_export_batch_id", "bookings", ["export_batch_id"])

    # SQLite cannot add a constraint to an existing table; dev SQLite DBs get it
    # from ``create_all`` instead.
    if op.get_bind().dialect.name != "sqlite":
        fks = {fk.get("name") for fk in insp.get_foreign_keys("bookings")}
        if "fk_bookings_export_batch_id" not in fks:
            op.create_foreign_key(
                "fk_bookings_export_batch_id",
                "bookings",
                "export_batches",
                ["export_batch_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    insp = _inspector()
    if op.get_bind().dialect.name != "sqlite":
        fks = {fk.get("name") for fk in insp.get_foreign_keys("bookings")}
        if "fk_bookings_export_batch_id" in fks:
            op.drop_constraint("fk_bookings_export_batch_id", "bookings", type_="foreignkey")
    indexes = {i["name"] for i in insp.get_indexes("bookings")}
    if "ix_bookings_export_batch_id" in indexes:
        op.drop_index("ix_bookings_export_batch_id", table_name="bookings")
    booking_columns = {c["name"] for c in insp.get_columns("bookings")}
    with op.batch_alter_table("bookings") as batch:
        if "exported_at" in booking_columns:
            batch.drop_column("exported_at")
        if "export_batch_id" in booking_columns:
            batch.drop_column("export_batch_id")
    if "export_batches" in set(insp.get_table_names()):
        op.drop_table("export_batches")
