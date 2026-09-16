"""Documents (Rechnungen/Belege) — phase 1 of the brainstorm."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money

DocumentStatus = Literal["offen", "bezahlt", "exportiert", "fehler"]
DocumentDirection = Literal["eingang", "ausgang"]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    direction: str
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
    contact_email: str
    mahnstufe: int
    mahnung_sent_at: datetime | None
    #: B-79 — when our own invoice went to the customer; null = written, not sent.
    sent_at: datetime | None = None
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
    direction: DocumentDirection | None = None
    contact_email: str | None = Field(default=None, max_length=255)
    kt_soll: str | None = Field(default=None, max_length=20)
    kt_haben: str | None = Field(default=None, max_length=20)
    mwst_code: str | None = Field(default=None, max_length=10)
    mwst_pct: str | None = Field(default=None, max_length=10)


class DocumentUploadResult(BaseModel):
    filename: str
    ok: bool
    document: DocumentOut | None = None
    error: str | None = None
    #: Maschinenlesbarer Grund, wenn `ok` falsch ist — z. B. `plan_limit_erreicht`
    #: (B-23) oder `http_413` (B-54). Der Upload ist ein Stapel: eine abgelehnte
    #: Datei beendet ihn nicht, und die Antwort bleibt 200. Ohne diesen Code
    #: müsste die Oberfläche den deutschen Fehlertext parsen, um zwischen
    #: "falsches Dateiformat" und "Abo aufgebraucht" zu unterscheiden.
    code: str = ""


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
