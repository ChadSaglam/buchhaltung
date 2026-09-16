"""E-Mail-Eingang (B-69)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MailSettingsOut(BaseModel):
    adresse: str = ""
    aktiv: bool = True
    allow_list: str = ""
    absender: list[str] = Field(default_factory=list)
    bereit: bool = False
    imap: bool = False
    webhook: bool = False


class MailSettingsUpdate(BaseModel):
    aktiv: bool | None = None
    allow_list: str | None = Field(default=None, max_length=4000)


class AbsenderRequest(BaseModel):
    adresse: str = Field(min_length=3, max_length=255)


class EmailMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_addr: str
    subject: str
    status: str
    reason: str
    attachment_count: int
    document_count: int
    sent_at: datetime | None
    created_at: datetime | None


class EmailEingangResponse(BaseModel):
    einstellungen: MailSettingsOut
    nachrichten: list[EmailMessageOut]
    belege_24h: int
    abgelehnt: int


class AbrufResponse(BaseModel):
    geholt: int
    hinweis: str = ""
