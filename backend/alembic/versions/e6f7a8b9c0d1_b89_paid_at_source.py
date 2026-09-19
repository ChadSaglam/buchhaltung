"""B-89: a till receipt paid by card is not an open payable

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-18

First real run, 2026-09-17: a Landi/Agrola fuel receipt was read correctly in
every field and then landed as ``status = 'offen'``. The receipt says
``Erhalten: MASTERCARD 58.48`` — the money left the account at the till. There
is no creditor and nothing is owed, but Offene Posten and the Heute card
present every ``offen`` document as *"Was schulden wir"*. Scan a month of fuel
receipts and the product invents a debt.

``status`` keeps both of its meanings; this column separates them. ``offen``
still means *not yet reconciled against a bank line*, which is true for a card
receipt and is what the Abgleich needs. ``paid_at_source`` says the money is
already gone, and the three places that read ``offen`` as *owed* — Offene
Posten, the liquidity forecast, the year-end payables check — filter on it.

Existing rows default to False: a document already in the database was entered
before the checkbox existed, and assuming it is unpaid is the safe direction.
The alternative (back-filling from the raw OCR text) would silently rewrite the
owner's books on a heuristic.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as b:
        b.add_column(sa.Column("paid_at_source", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("documents") as b:
        b.drop_column("paid_at_source")
