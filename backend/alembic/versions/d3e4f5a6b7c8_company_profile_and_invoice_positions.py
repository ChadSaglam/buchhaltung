"""company_profiles + invoice_positions — Rechnungen schreiben (B-68)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-15

Idempotent: dev databases created with ``create_all`` already carry both tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "company_profiles" not in tables:
        op.create_table(
            "company_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=70), nullable=False, server_default=""),
            sa.Column("strasse", sa.String(length=70), nullable=False, server_default=""),
            sa.Column("hausnummer", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("plz", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("ort", sa.String(length=35), nullable=False, server_default=""),
            sa.Column("land", sa.String(length=2), nullable=False, server_default="CH"),
            sa.Column("iban", sa.String(length=34), nullable=False, server_default=""),
            sa.Column("mwst_nr", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("telefon", sa.String(length=50), nullable=False, server_default=""),
            sa.Column("zahlungsfrist_tage", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("konto_debitoren", sa.String(length=20), nullable=False, server_default="1100"),
            sa.Column("konto_ertrag", sa.String(length=20), nullable=False, server_default="3000"),
            sa.Column("konto_bank", sa.String(length=20), nullable=False, server_default="1020"),
            sa.Column("mwst_code", sa.String(length=10), nullable=False, server_default="V81"),
            sa.Column("mwst_pct", sa.String(length=10), nullable=False, server_default="-8.10"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tenant_id", name="uq_company_profiles_tenant_id"),
        )
        op.create_index("ix_company_profiles_tenant_id", "company_profiles", ["tenant_id"])

    if "invoice_positions" not in tables:
        op.create_table(
            "invoice_positions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "document_id",
                sa.Integer(),
                sa.ForeignKey("documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("bezeichnung", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("menge", sa.Float(), nullable=False, server_default="1"),
            sa.Column("einheit", sa.String(length=20), nullable=False, server_default=""),
            sa.Column("einzelpreis", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_invoice_positions_tenant_id", "invoice_positions", ["tenant_id"])
        op.create_index("ix_invoice_positions_document_id", "invoice_positions", ["document_id"])
        op.create_index("ix_invoice_positions_tenant_document", "invoice_positions", ["tenant_id", "document_id"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "invoice_positions" in tables:
        op.drop_table("invoice_positions")
    if "company_profiles" in tables:
        op.drop_table("company_profiles")
