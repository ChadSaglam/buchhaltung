"""Documents (Rechnungen/Belege) — phase 1 of the brainstorm."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money

DocumentStatus = Literal["offen", "bezahlt", "exportiert", "fehler"]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    filename: str
    vendor: str
    amount: float | None
    currency: str
    invoice_no: str
    invoice_date: date | None
    due_date: date | None
    qr_iban: str
    qr_reference: str
    qr_message: str
    extraction_source: str
    extraction_confidence: float
    kt_soll: str
    kt_haben: str
    mwst_code: str
    mwst_pct: str
    classification_confidence: float
    booking_id: int | None
    error: str
    created_at: datetime | None
    updated_at: datetime | None


class DocumentUpdate(BaseModel):
    """Fields the user may correct on an open document."""

    vendor: str | None = Field(default=None, max_length=255)
    amount: Money | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    invoice_no: str | None = Field(default=None, max_length=100)
    invoice_date: date | None = None
    due_date: date | None = None
    status: DocumentStatus | None = None
    kt_soll: str | None = Field(default=None, max_length=20)
    kt_haben: str | None = Field(default=None, max_length=20)
    mwst_code: str | None = Field(default=None, max_length=10)
    mwst_pct: str | None = Field(default=None, max_length=10)


class DocumentUploadResult(BaseModel):
    filename: str
    ok: bool
    document: DocumentOut | None = None
    error: str | None = None


class DocumentUploadResponse(BaseModel):
    results: list[DocumentUploadResult]
    created: int
    failed: int


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    count: int


class DocumentSummary(BaseModel):
    offen: int
    offen_betrag: float
    ueberfaellig: int
    bezahlt: int
    exportiert: int
    fehler: int
