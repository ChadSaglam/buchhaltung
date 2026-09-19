"""EmailMessage — one delivered e-mail, kept as the receipt of the intake (B-69).

Two jobs: never ingest the same message twice (``message_id`` is unique per
tenant), and let the owner see *why* something did not arrive — a rejected
sender is the normal case on day one, and the fix is one click.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

STATUS_VERARBEITET = "verarbeitet"
STATUS_ABGELEHNT = "abgelehnt"
STATUS_LEER = "leer"
STATUS_FEHLER = "fehler"
MAIL_STATUSES = (STATUS_VERARBEITET, STATUS_ABGELEHNT, STATUS_LEER, STATUS_FEHLER)


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "message_id", name="uq_email_messages_tenant_message"),
        Index("ix_email_messages_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    message_id: Mapped[str] = mapped_column(String(255), default="")
    from_addr: Mapped[str] = mapped_column(String(255), default="")
    to_addr: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(255), default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=STATUS_VERARBEITET)
    reason: Mapped[str] = mapped_column(String(255), default="")
    attachment_count: Mapped[int] = mapped_column(Integer, default=0)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    document_ids: Mapped[str] = mapped_column(Text, default="")  # comma separated, for the UI

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
