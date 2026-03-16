"""Pickled ML model storage — tenant-scoped."""
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ClassifierModel(Base):
    __tablename__ = "classifier_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, index=True)
    model_blob: Mapped[bytes] = mapped_column(LargeBinary)
    total_samples: Mapped[int] = mapped_column(Integer, default=0)
    num_classes: Mapped[int] = mapped_column(Integer, default=0)
    cv_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    train_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    sklearn_version: Mapped[str] = mapped_column(String(20), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
