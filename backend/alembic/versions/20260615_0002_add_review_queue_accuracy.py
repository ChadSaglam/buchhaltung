"""add review queue, accuracy history, threshold column

Revision ID: 20260615_0002
Revises: 20260611_0001
Create Date: 2026-06-15 18:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20260615_0002"
down_revision = "20260611_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scanner_configs",
        sa.Column("review_confidence_threshold", sa.Float(), nullable=False, server_default="0.80"),
    )

    op.create_table(
        "review_queue_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("beschreibung", sa.Text(), nullable=False),
        sa.Column("betrag", sa.Float(), nullable=False, server_default="0"),
        sa.Column("predicted_soll", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("predicted_haben", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("predicted_mwst_code", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("predicted_mwst_pct", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("resolved_soll", sa.String(length=20), nullable=True),
        sa.Column("resolved_haben", sa.String(length=20), nullable=True),
        sa.Column("resolved_mwst_code", sa.String(length=10), nullable=True),
        sa.Column("resolved_mwst_pct", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_queue_items_tenant_id"), "review_queue_items", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_review_queue_items_status"), "review_queue_items", ["status"], unique=False)

    op.create_table(
        "accuracy_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("cv_accuracy", sa.Float(), nullable=True),
        sa.Column("train_accuracy", sa.Float(), nullable=True),
        sa.Column("total_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("num_classes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sklearn_version", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accuracy_history_tenant_id"), "accuracy_history", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_accuracy_history_tenant_id"), table_name="accuracy_history")
    op.drop_table("accuracy_history")
    op.drop_index(op.f("ix_review_queue_items_status"), table_name="review_queue_items")
    op.drop_index(op.f("ix_review_queue_items_tenant_id"), table_name="review_queue_items")
    op.drop_table("review_queue_items")
    op.drop_column("scanner_configs", "review_confidence_threshold")