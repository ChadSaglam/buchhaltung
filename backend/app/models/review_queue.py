"""Confidence-threshold review queue — tenant-scoped."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import Chf


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"
    # B-28: the queue is always "this tenant, still pending, least confident
    # first". Measured on 60k rows: 1'603 buffers and 5'379 rows discarded by a
    # filter → 521 buffers and none.
    __table_args__ = (
        Index("ix_review_queue_tenant_status_confidence", "tenant_id", "status", "confidence", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)

    beschreibung: Mapped[str] = mapped_column(Text, nullable=False)
    betrag: Mapped[float] = mapped_column(Chf, default=0.0, nullable=False)

    predicted_soll: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    predicted_haben: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    predicted_mwst_code: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    predicted_mwst_pct: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="", nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)

    resolved_soll: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved_haben: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved_mwst_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    resolved_mwst_pct: Mapped[str | None] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
