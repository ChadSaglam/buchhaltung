"""Lohn: settings, employees, payslips (B-72)

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-09-16

Money is ``Numeric(12, 2)`` (models/types.py ``Chf``); rates are ``Float``,
because a percentage is not money and four decimal places of UVG premium are
normal. Every rate that comes from an insurance contract or a canton is
nullable with no server default — see models/lohn_settings.py for why a missing
rate must stay missing.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHF = sa.Numeric(12, 2)


def upgrade() -> None:
    op.create_table(
        "lohn_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("ahv_satz_an", sa.Float(), nullable=False, server_default="5.3"),
        sa.Column("alv_satz_an", sa.Float(), nullable=False, server_default="1.1"),
        sa.Column("alv_jahresgrenze", CHF, nullable=False, server_default="148200"),
        sa.Column("uvg_bu_satz", sa.Float(), nullable=True),
        sa.Column("uvg_nbu_satz", sa.Float(), nullable=True),
        sa.Column("uvgz_satz_an", sa.Float(), nullable=True),
        sa.Column("uvgz_satz_ag", sa.Float(), nullable=True),
        sa.Column("ktg_satz_an", sa.Float(), nullable=True),
        sa.Column("ktg_satz_ag", sa.Float(), nullable=True),
        sa.Column("fak_satz", sa.Float(), nullable=True),
        sa.Column("verwaltungskosten_satz", sa.Float(), nullable=True),
        sa.Column("konto_lohnaufwand", sa.String(length=20), nullable=False, server_default="5000"),
        sa.Column("konto_sozialversicherung", sa.String(length=20), nullable=False, server_default="5700"),
        sa.Column("konto_verbindlichkeit", sa.String(length=20), nullable=False, server_default="2270"),
        sa.Column("konto_bank", sa.String(length=20), nullable=False, server_default="1020"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_lohn_settings_tenant_id"),
    )
    op.create_index(op.f("ix_lohn_settings_tenant_id"), "lohn_settings", ["tenant_id"], unique=False)

    op.create_table(
        "mitarbeiter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("vorname", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("ahv_nummer", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("geburtsdatum", sa.Date(), nullable=True),
        sa.Column("eintritt", sa.Date(), nullable=True),
        sa.Column("austritt", sa.Date(), nullable=True),
        sa.Column("pensum", sa.Float(), nullable=False, server_default="100"),
        sa.Column("monatslohn", CHF, nullable=False, server_default="0"),
        sa.Column("dreizehnter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("kinder", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kanton", sa.String(length=2), nullable=False, server_default=""),
        sa.Column("quellensteuer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quellensteuer_satz", sa.Float(), nullable=True),
        sa.Column("quellensteuer_tarif", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("bvg_an_monat", CHF, nullable=True),
        sa.Column("bvg_ag_monat", CHF, nullable=True),
        sa.Column("iban", sa.String(length=34), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mitarbeiter_tenant_id"), "mitarbeiter", ["tenant_id"], unique=False)
    op.create_index("ix_mitarbeiter_tenant_aktiv", "mitarbeiter", ["tenant_id", "austritt"], unique=False)

    op.create_table(
        "lohnabrechnungen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("mitarbeiter_id", sa.Integer(), nullable=False),
        sa.Column("jahr", sa.Integer(), nullable=False),
        sa.Column("monat", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="entwurf"),
        sa.Column("grundlohn", CHF, nullable=False, server_default="0"),
        sa.Column("dreizehnter", CHF, nullable=False, server_default="0"),
        sa.Column("zulagen", CHF, nullable=False, server_default="0"),
        sa.Column("brutto", CHF, nullable=False, server_default="0"),
        sa.Column("ahv_satz", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ahv_betrag", CHF, nullable=False, server_default="0"),
        sa.Column("alv_satz", sa.Float(), nullable=False, server_default="0"),
        sa.Column("alv_betrag", CHF, nullable=False, server_default="0"),
        sa.Column("alv_basis", CHF, nullable=False, server_default="0"),
        sa.Column("nbu_satz", sa.Float(), nullable=False, server_default="0"),
        sa.Column("nbu_betrag", CHF, nullable=False, server_default="0"),
        sa.Column("uvgz_satz", sa.Float(), nullable=False, server_default="0"),
        sa.Column("uvgz_betrag", CHF, nullable=False, server_default="0"),
        sa.Column("ktg_satz", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ktg_betrag", CHF, nullable=False, server_default="0"),
        sa.Column("bvg_betrag", CHF, nullable=False, server_default="0"),
        sa.Column("quellensteuer_satz", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quellensteuer_betrag", CHF, nullable=False, server_default="0"),
        sa.Column("abzuege", CHF, nullable=False, server_default="0"),
        sa.Column("netto", CHF, nullable=False, server_default="0"),
        sa.Column("ag_ahv", CHF, nullable=False, server_default="0"),
        sa.Column("ag_alv", CHF, nullable=False, server_default="0"),
        sa.Column("ag_bu", CHF, nullable=False, server_default="0"),
        sa.Column("ag_uvgz", CHF, nullable=False, server_default="0"),
        sa.Column("ag_ktg", CHF, nullable=False, server_default="0"),
        sa.Column("ag_fak", CHF, nullable=False, server_default="0"),
        sa.Column("ag_verwaltungskosten", CHF, nullable=False, server_default="0"),
        sa.Column("ag_bvg", CHF, nullable=False, server_default="0"),
        sa.Column("ag_total", CHF, nullable=False, server_default="0"),
        sa.Column("abgerechnet_am", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mitarbeiter_id"], ["mitarbeiter.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "mitarbeiter_id", "jahr", "monat", name="uq_lohnabrechnung_periode"),
    )
    op.create_index(op.f("ix_lohnabrechnungen_tenant_id"), "lohnabrechnungen", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_lohnabrechnungen_mitarbeiter_id"), "lohnabrechnungen", ["mitarbeiter_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_lohnabrechnungen_mitarbeiter_id"), table_name="lohnabrechnungen")
    op.drop_index(op.f("ix_lohnabrechnungen_tenant_id"), table_name="lohnabrechnungen")
    op.drop_table("lohnabrechnungen")
    op.drop_index("ix_mitarbeiter_tenant_aktiv", table_name="mitarbeiter")
    op.drop_index(op.f("ix_mitarbeiter_tenant_id"), table_name="mitarbeiter")
    op.drop_table("mitarbeiter")
    op.drop_index(op.f("ix_lohn_settings_tenant_id"), table_name="lohn_settings")
    op.drop_table("lohn_settings")
