"""Per-tenant classifier accuracy history — one row per training run."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AccuracyHistory(Base):
    __tablename__ = "accuracy_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)

    cv_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    train_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    num_classes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sklearn_version: Mapped[str] = mapped_column(String(20), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)