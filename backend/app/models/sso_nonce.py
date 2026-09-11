"""Used SSO token ids (contracts/sso.md: `jti` is single-use).

A table rather than an in-process set so replay protection holds across API
workers/replicas. Rows are purged opportunistically once expired.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SsoNonce(Base):
    __tablename__ = "sso_nonces"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
