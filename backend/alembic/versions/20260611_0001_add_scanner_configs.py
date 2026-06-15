"""add scanner configs

Revision ID: 20260611_0001
Revises: 
Create Date: 2026-06-11 06:20:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260611_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scanner_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("ocr_provider", sa.String(length=50), nullable=False),
        sa.Column("vision_provider", sa.String(length=50), nullable=False),
        sa.Column("fallback_provider", sa.String(length=50), nullable=True),
        sa.Column("ollama_base_url", sa.String(length=500), nullable=False),
        sa.Column("default_ollama_model", sa.String(length=255), nullable=True),
        sa.Column("ocr_command", sa.Text(), nullable=True),
        sa.Column("pdf_ocr_enabled", sa.Boolean(), nullable=False),
        sa.Column("invoice_matching_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_classification_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_scanner_configs_tenant_id"),
    )
    op.create_index(op.f("ix_scanner_configs_tenant_id"), "scanner_configs", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scanner_configs_tenant_id"), table_name="scanner_configs")
    op.drop_table("scanner_configs")