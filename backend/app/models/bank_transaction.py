"""BankTransaction — one line of a Kontoauszug, kept as a thing (brainstorm phase 2/3).

Until now the parsed lines only lived in the browser until "speichern"; matching
needs them persisted so a line can be open today and reconciled tomorrow.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import Chf

TX_STATUS_OFFEN = "offen"
TX_STATUS_ZUGEORDNET = "zugeordnet"
TX_STATUS_GEBUCHT = "gebucht"
TX_STATUS_IGNORIERT = "ignoriert"
TX_STATUSES = (TX_STATUS_OFFEN, TX_STATUS_ZUGEORDNET, TX_STATUS_GEBUCHT, TX_STATUS_IGNORIERT)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        Index("ix_bank_transactions_tenant_status", "tenant_id", "status"),
        Index("ix_bank_transactions_tenant_amount", "tenant_id", "amount"),
        # Same statement, same line → one row (re-uploading a PDF must not duplicate).
        Index("uq_bank_transactions_dedup", "tenant_id", "dedup_key", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=TX_STATUS_OFFEN)

    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    booking_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # Signed: negative = Belastung (money out), positive = Gutschrift (money in).
    amount: Mapped[float] = mapped_column(Chf, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="CHF")
    # QRR/SCOR reference when the statement carries one (camt.053 always does, PDF rarely).
    reference: Mapped[str] = mapped_column(String(27), default="")
    counterparty: Mapped[str] = mapped_column(String(255), default="")

    statement_key: Mapped[str] = mapped_column(String(255), default="")  # storage key of the uploaded file
    dedup_key: Mapped[str] = mapped_column(String(64), default="")  # sha256 of tenant+date+amount+description
    source: Mapped[str] = mapped_column(String(20), default="pdf")  # pdf | camt053 | manual

    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
