"""ExportBatch — one Banana hand-off with a status (brainstorm 2026-09-13, phase 4).

Exporting used to be a download: nothing remembered what had already been sent,
so the next file repeated everything. A batch is the memory. Bookings carry
``export_batch_id`` + ``exported_at``; the next export offers only what is new,
and re-downloading an old batch renders exactly the same bytes (``checksum``).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

FORMAT_BANANA = "banana"


class ExportBatch(Base):
    __tablename__ = "export_batches"
    __table_args__ = (Index("ix_export_batches_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(20), default=FORMAT_BANANA)
    filename: Mapped[str] = mapped_column(String(255), default="")

    booking_count: Mapped[int] = mapped_column(Integer, default=0)
    total_betrag: Mapped[float] = mapped_column(Float, default=0.0)
    total_mwst: Mapped[float] = mapped_column(Float, default=0.0)
    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    # sha256 of the rendered file — proof that a re-download is the same hand-off.
    checksum: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(String(255), default="")

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
