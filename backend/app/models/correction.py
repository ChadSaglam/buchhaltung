"""Corrections log — tenant-scoped."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    beschreibung: Mapped[str] = mapped_column(Text)
    original_soll: Mapped[str] = mapped_column(String(20))
    original_haben: Mapped[str] = mapped_column(String(20))
    corrected_soll: Mapped[str] = mapped_column(String(20))
    corrected_haben: Mapped[str] = mapped_column(String(20))
    corrected_mwst_code: Mapped[str] = mapped_column(String(10), default="")
    corrected_mwst_pct: Mapped[str] = mapped_column(String(10), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
