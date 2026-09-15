"""Match — a proposed or confirmed link between a Document and a BankTransaction.

One transaction can settle several documents (Sammelauftrag → n:1), so the link
is its own row rather than a column on either side. Every human decision here is
a training row for the match scorer (brainstorm phase 5).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MATCH_VORGESCHLAGEN = "vorgeschlagen"
MATCH_BESTAETIGT = "bestaetigt"
MATCH_ABGELEHNT = "abgelehnt"
MATCH_STATUSES = (MATCH_VORGESCHLAGEN, MATCH_BESTAETIGT, MATCH_ABGELEHNT)

# Why the engine proposed it — shown to the user instead of a bare percentage.
TIER_REFERENCE = "referenz"
TIER_AMOUNT_DATE = "betrag_datum"
TIER_SUBSET = "sammelauftrag"
TIER_MANUAL = "manuell"


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_tenant_status", "tenant_id", "status"),
        Index("ix_matches_transaction", "transaction_id"),
        Index("ix_matches_document", "document_id"),
        # A document/transaction pair exists once; re-running the engine updates it.
        Index("uq_matches_pair", "tenant_id", "document_id", "transaction_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("bank_transactions.id", ondelete="CASCADE"))

    status: Mapped[str] = mapped_column(String(20), default=MATCH_VORGESCHLAGEN)
    tier: Mapped[str] = mapped_column(String(20), default=TIER_AMOUNT_DATE)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(255), default="")
    # Part of this transaction that settles this document (a Sammelauftrag splits).
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
