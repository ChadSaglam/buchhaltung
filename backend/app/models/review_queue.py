"""Confidence-threshold review queue — tenant-scoped."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)

    beschreibung: Mapped[str] = mapped_column(Text, nullable=False)
    betrag: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

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