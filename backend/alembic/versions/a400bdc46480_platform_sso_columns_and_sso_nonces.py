"""platform SSO columns + sso_nonces (B-36)

chadev-platform/contracts/sso.md, tenant mirroring + shadow users:
  * `tenants.platform_tenant_id` — billing's tenant id (`tid`), unique, NULL
    for standalone tenants.
  * `users.platform_user_id` — billing's user id (`sub`), unique per tenant;
    `users.auth_source` — 'local' (password) | 'platform' (shadow user, no
    usable password). Existing rows default to 'local'.
  * `sso_nonces` — used token ids, so a token is single-use across workers.

Batch mode so SQLite (dev/test) can add the constraints too; on Postgres the
batch is a plain ALTER.

Revision ID: a400bdc46480
Revises: 55e64308d75f
Create Date: 2026-09-11 14:39:28.226717
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a400bdc46480'
down_revision: Union[str, None] = '55e64308d75f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sso_nonces',
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('jti'),
    )
    with op.batch_alter_table('tenants') as batch:
        batch.add_column(sa.Column('platform_tenant_id', sa.Integer(), nullable=True))
        batch.create_unique_constraint('uq_tenants_platform_tenant_id', ['platform_tenant_id'])
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('platform_user_id', sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column('auth_source', sa.String(length=16), server_default='local', nullable=False)
        )
        batch.create_unique_constraint('uq_users_tenant_platform_user', ['tenant_id', 'platform_user_id'])


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('uq_users_tenant_platform_user', type_='unique')
        batch.drop_column('auth_source')
        batch.drop_column('platform_user_id')
    with op.batch_alter_table('tenants') as batch:
        batch.drop_constraint('uq_tenants_platform_tenant_id', type_='unique')
        batch.drop_column('platform_tenant_id')
    op.drop_table('sso_nonces')
