"""MailSettings — the per-tenant rules for the e-mail intake (B-69).

The address itself is derived (``belege+<slug>@…``), not stored: it follows the
tenant slug and the deployment's domain. What *is* per tenant is whether the
door is open at all and who is allowed through it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MailSettings(Base):
    __tablename__ = "mail_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_mail_settings_tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # One entry per line: a full address (rechnung@lieferant.ch) or a whole
    # domain (@lieferant.ch). Empty means nothing is accepted — see services/email_intake.py.
    allow_list: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
