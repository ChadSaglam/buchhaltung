from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ScannerConfig(Base):
    __tablename__ = "scanner_configs"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_scanner_configs_tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    ocr_provider: Mapped[str] = mapped_column(String(50), default="custom-ocr", nullable=False)
    vision_provider: Mapped[str] = mapped_column(String(50), default="ollama", nullable=False)
    fallback_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)

    ollama_base_url: Mapped[str] = mapped_column(String(500), default="http://localhost:11434", nullable=False)
    default_ollama_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ocr_command: Mapped[str | None] = mapped_column(Text, nullable=True)

    pdf_ocr_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    invoice_matching_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_classification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    review_confidence_threshold: Mapped[float] = mapped_column(Float, default=0.80, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="scanner_config")  # noqa: F821
