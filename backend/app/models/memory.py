"""Memory model — exact-match lookup cache, tenant-scoped."""
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Memory(Base):
    __tablename__ = "memory"
    __table_args__ = (UniqueConstraint("tenant_id", "lookup_key", name="uq_tenant_memory"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    lookup_key: Mapped[str] = mapped_column(String(500))
    kt_soll: Mapped[str] = mapped_column(String(20))
    kt_haben: Mapped[str] = mapped_column(String(20))
    mwst_code: Mapped[str] = mapped_column(String(10), default="")
    mwst_pct: Mapped[str] = mapped_column(String(10), default="")
