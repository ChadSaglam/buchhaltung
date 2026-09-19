"""Offene Posten + Mahnung (B-65)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.document import DocumentOut


class OpenItemOut(BaseModel):
    document: DocumentOut
    due_date: date | None
    days_overdue: int
    bucket: str  # nicht_faellig | 1_30 | 31_60 | 61_90 | ueber_90
    mahnbar: bool


class SideOut(BaseModel):
    """Debitoren (they owe us) or Kreditoren (we owe) — the same shape twice."""

    count: int
    total: float
    overdue_count: int
    overdue_total: float
    buckets: dict[str, float]
    items: list[OpenItemOut]


class OffenePostenResponse(BaseModel):
    debitoren: SideOut
    kreditoren: SideOut


class MahnungDraft(BaseModel):
    document_id: int
    stufe: int
    stufe_label: str
    empfaenger: str
    empfaenger_email: str
    subject: str
    text: str
    html_url: str
    recorded: bool = False


class MahnungRequest(BaseModel):
    stufe: int | None = Field(default=None, ge=1, le=3)
