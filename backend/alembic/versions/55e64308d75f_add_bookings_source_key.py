"""add bookings.source_key (B-09)

Storage key (`receipts/<tenant_id>/<uuid>.<ext>`) of the uploaded document a
booking was created from; NULL for manual rows.

Revision ID: 55e64308d75f
Revises: 52eb7a4363f0
Create Date: 2026-09-10 17:19:14.601417
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '55e64308d75f'
down_revision: Union[str, None] = '52eb7a4363f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('source_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'source_key')
