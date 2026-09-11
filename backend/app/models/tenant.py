"""Tenant model — each organization or individual account.

Columns follow the platform contract (chadev-platform/contracts/tenant.md):
`slug`, `subscription_plan`, `trial_ends_at`, `is_active` are shared with billing.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("platform_tenant_id", name="uq_tenants_platform_tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # Nullable: tenants created before the contract have no slug until backfilled.
    slug: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    # Stays String(50) — the contract says str(20), but shrinking would truncate data.
    subscription_plan: Mapped[str] = mapped_column(String(50), default="free")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # billing tenant id (`tid` in the SSO token, contracts/sso.md). Set on the
    # first SSO hop that mirrors the tenant; NULL for standalone tenants.
    platform_tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="tenant")  # noqa: F821
    scanner_config: Mapped["ScannerConfig | None"] = relationship(  # noqa: F821
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
