"""InvoicePosition — the lines of an invoice we write ourselves (B-68).

The invoice header *is* a ``Document`` with ``direction = ausgang``, so it flows
straight into Offene Posten, Mahnung and the Abgleich without a second concept.
Only the line items have nowhere to live — this is that table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvoicePosition(Base):
    __tablename__ = "invoice_positions"
    __table_args__ = (Index("ix_invoice_positions_tenant_document", "tenant_id", "document_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)

    position: Mapped[int] = mapped_column(Integer, default=1)
    bezeichnung: Mapped[str] = mapped_column(String(255), default="")
    menge: Mapped[float] = mapped_column(Float, default=1.0)
    einheit: Mapped[str] = mapped_column(String(20), default="")
    einzelpreis: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
