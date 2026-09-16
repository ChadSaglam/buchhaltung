"""Rechnungen schreiben + Firmenprofil (B-68)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money
from app.schemas.document import DocumentOut


class FirmaProfil(BaseModel):
    """The tenant's own data — absender on the letter, creditor in the QR payload."""

    model_config = ConfigDict(from_attributes=True)

    name: str = ""
    strasse: str = ""
    hausnummer: str = ""
    plz: str = ""
    ort: str = ""
    land: str = "CH"
    iban: str = ""
    mwst_nr: str = ""
    email: str = ""
    telefon: str = ""
    zahlungsfrist_tage: int = 30
    konto_debitoren: str = ""
    konto_ertrag: str = ""
    konto_bank: str = ""
    mwst_code: str = ""
    mwst_pct: str = ""
    #: B-71 — effective corporate income tax rate in percent; None = not set.
    gewinnsteuer_satz: float | None = None


class FirmaProfilOut(FirmaProfil):
    """Plus what the UI needs to say *why* an invoice cannot be written yet."""

    iban_formatiert: str = ""
    qr_iban: bool = False
    referenz_typ: str = ""
    fehlt: list[str] = Field(default_factory=list)
    bereit: bool = False


class FirmaProfilUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=70)
    strasse: str | None = Field(default=None, max_length=70)
    hausnummer: str | None = Field(default=None, max_length=16)
    plz: str | None = Field(default=None, max_length=16)
    ort: str | None = Field(default=None, max_length=35)
    land: str | None = Field(default=None, min_length=2, max_length=2)
    iban: str | None = Field(default=None, max_length=34)
    mwst_nr: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    telefon: str | None = Field(default=None, max_length=50)
    zahlungsfrist_tage: int | None = Field(default=None, ge=0, le=365)
    konto_debitoren: str | None = Field(default=None, max_length=20)
    konto_ertrag: str | None = Field(default=None, max_length=20)
    konto_bank: str | None = Field(default=None, max_length=20)
    mwst_code: str | None = Field(default=None, max_length=10)
    mwst_pct: str | None = Field(default=None, max_length=10)
    # B-71: null removes the rate again; 60 is well past any Swiss rate, so it is a typo.
    gewinnsteuer_satz: float | None = Field(default=None, ge=0, le=60)


class PositionIn(BaseModel):
    bezeichnung: str = Field(min_length=1, max_length=255)
    menge: float = Field(default=1.0, ge=0, le=1e6)
    einheit: str = Field(default="", max_length=20)
    einzelpreis: Money = 0.0


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    bezeichnung: str
    menge: float
    einheit: str
    einzelpreis: float
    betrag: float = 0.0


class KundeIn(BaseModel):
    name: str = Field(min_length=1, max_length=70)
    strasse: str = Field(default="", max_length=70)
    hausnummer: str = Field(default="", max_length=16)
    plz: str = Field(default="", max_length=16)
    ort: str = Field(default="", max_length=35)
    land: str = Field(default="CH", min_length=2, max_length=2)
    email: str = Field(default="", max_length=255)


class RechnungCreate(BaseModel):
    kunde: KundeIn
    positionen: list[PositionIn] = Field(min_length=1, max_length=60)
    rechnungsdatum: date | None = None
    faellig_am: date | None = None
    bemerkung: str = Field(default="", max_length=140)


class RechnungOut(BaseModel):
    document: DocumentOut
    positionen: list[PositionOut]
    netto: float
    mwst: float
    total: float
    referenz_typ: str
    referenz_formatiert: str
    html_url: str
    booking_id: int | None = None


class RechnungListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_no: str
    vendor: str
    amount: float | None
    status: str
    invoice_date: date | None
    due_date: date | None
    qr_reference: str


class RechnungListResponse(BaseModel):
    items: list[RechnungListItem]
    count: int
    naechste_nummer: str
