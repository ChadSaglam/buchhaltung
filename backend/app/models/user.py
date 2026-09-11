"""User model with tenant FK."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

AUTH_SOURCE_LOCAL = "local"
AUTH_SOURCE_PLATFORM = "platform"
# Not a bcrypt hash, so `verify_password` can never accept it.
PLATFORM_PASSWORD_SENTINEL = "!platform"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "platform_user_id", name="uq_users_tenant_platform_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(50), default="owner")
    # Platform SSO (contracts/sso.md, ADR-001 amendment): `platform_user_id` is
    # billing's `sub`; `auth_source` is "local" for accounts with a password
    # and "platform" for shadow users, whose `password_hash` is the unusable
    # sentinel `PLATFORM_PASSWORD_SENTINEL` — `/api/auth/login` refuses them
    # before it ever looks at the password.
    platform_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(16), default="local", server_default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship(back_populates="users")  # noqa: F821
