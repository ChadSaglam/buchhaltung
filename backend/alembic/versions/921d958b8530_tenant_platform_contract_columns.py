"""tenant platform contract columns (B-26)

Aligns `tenants` with chadev-platform/contracts/tenant.md:
  * `plan` is renamed to `subscription_plan` — a rename, not drop/add, so
    existing rows keep their value. Width stays String(50) to avoid truncation.
  * `slug` (unique, nullable — old tenants are not backfilled here),
    `trial_ends_at` and `is_active` (server default true) are added.

Revision ID: 921d958b8530
Revises: 73f03c35bbed
Create Date: 2026-09-10 11:17:11.600781
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '921d958b8530'
down_revision: Union[str, None] = '73f03c35bbed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('tenants', 'plan', new_column_name='subscription_plan')
    op.add_column('tenants', sa.Column('slug', sa.String(length=100), nullable=True))
    op.add_column('tenants', sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'tenants',
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_unique_constraint('uq_tenants_slug', 'tenants', ['slug'])


def downgrade() -> None:
    op.drop_constraint('uq_tenants_slug', 'tenants', type_='unique')
    op.drop_column('tenants', 'is_active')
    op.drop_column('tenants', 'trial_ends_at')
    op.drop_column('tenants', 'slug')
    op.alter_column('tenants', 'subscription_plan', new_column_name='plan')
