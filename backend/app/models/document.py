"""Document — a Rechnung/Beleg as a *thing* with a life cycle (brainstorm 2026-09-13, phase 1).

Today's bookings are flat rows; a document knows where its file is, what was
read from it (QR-bill first, vision/OCR second), what the classifier proposed,
whether it has been paid (matched to a bank line in phase 3) and whether it
went to Banana (phase 4).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import Chf

STATUS_OFFEN = "offen"
STATUS_BEZAHLT = "bezahlt"
STATUS_EXPORTIERT = "exportiert"
STATUS_FEHLER = "fehler"
DOCUMENT_STATUSES = (STATUS_OFFEN, STATUS_BEZAHLT, STATUS_EXPORTIERT, STATUS_FEHLER)

KIND_RECHNUNG = "rechnung"
KIND_BELEG = "beleg"

# Which way the money flows (B-65). Eingang = a supplier invoice we owe
# (Kreditor); Ausgang = our own invoice a customer owes us (Debitor) — only an
# Ausgang can be gemahnt.
DIRECTION_EINGANG = "eingang"
DIRECTION_AUSGANG = "ausgang"
DIRECTIONS = (DIRECTION_EINGANG, DIRECTION_AUSGANG)

MAX_MAHNSTUFE = 3


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_tenant_status", "tenant_id", "status"),
        Index("ix_documents_tenant_reference", "tenant_id", "qr_reference"),
        Index("ix_documents_tenant_direction_status", "tenant_id", "direction", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=KIND_RECHNUNG)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_OFFEN)
    direction: Mapped[str] = mapped_column(String(10), default=DIRECTION_EINGANG)

    # The file (services/receipts.py key) and what the user uploaded it as.
    file_key: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255), default="")

    # What was read from it.
    vendor: Mapped[str] = mapped_column(String(255), default="")
    amount: Mapped[float | None] = mapped_column(Chf, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="CHF")
    invoice_no: Mapped[str] = mapped_column(String(100), default="")
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Swiss QR-bill: IBAN + QRR/SCOR reference — the exact matching key for phase 3.
    qr_iban: Mapped[str] = mapped_column(String(34), default="")
    qr_reference: Mapped[str] = mapped_column(String(27), default="")
    qr_message: Mapped[str] = mapped_column(String(140), default="")
    extraction_source: Mapped[str] = mapped_column(String(20), default="")  # qr | vision | ocr | manual
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_json: Mapped[str] = mapped_column(Text, default="")

    # What the classifier proposed (editable on the document until it is booked).
    kt_soll: Mapped[str] = mapped_column(String(20), default="")
    kt_haben: Mapped[str] = mapped_column(String(20), default="")
    mwst_code: Mapped[str] = mapped_column(String(10), default="")
    mwst_pct: Mapped[str] = mapped_column(String(10), default="")
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Offene Posten (B-65): who to remind, and how often it has happened.
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    mahnstufe: Mapped[int] = mapped_column(Integer, default=0)
    mahnung_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # B-79: when our own invoice actually went to the customer. None = never sent,
    # which is also the difference between "written" and "out the door".
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    error: Mapped[str] = mapped_column(String(255), default="")
    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
