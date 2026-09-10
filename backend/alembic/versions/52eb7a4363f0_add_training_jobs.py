"""add training_jobs (B-08)

Queue between the API (inserts) and the worker process (claims + trains), so
the training worker can run outside the API process.

Revision ID: 52eb7a4363f0
Revises: 4c7e2a91b0d3
Create Date: 2026-09-10 17:11:49.773816
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '52eb7a4363f0'
down_revision: Union[str, None] = '4c7e2a91b0d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('training_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_jobs_status'), 'training_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_training_jobs_tenant_id'), 'training_jobs', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_training_jobs_tenant_id'), table_name='training_jobs')
    op.drop_index(op.f('ix_training_jobs_status'), table_name='training_jobs')
    op.drop_table('training_jobs')
