"""Training data rows — tenant-scoped, replaces CSV."""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class TrainingRow(Base):
    __tablename__ = "training_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    beschreibung: Mapped[str] = mapped_column(Text)
    kt_soll: Mapped[str] = mapped_column(String(20))
    kt_haben: Mapped[str] = mapped_column(String(20), default="")
    mwst_code: Mapped[str] = mapped_column(String(10), default="")
    mwst_pct: Mapped[str] = mapped_column(String(10), default="")
