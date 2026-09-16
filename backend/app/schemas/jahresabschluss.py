"""Jahresabschluss (B-70)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.export_batch import ExportCheck


class PositionOut(BaseModel):
    konto: str
    bezeichnung: str
    saldo: float


class GruppeOut(BaseModel):
    key: str
    label: str
    positionen: list[PositionOut]
    total: float


class AbschreibungOut(BaseModel):
    konto: str
    bezeichnung: str
    buchwert: float
    satz: float
    betrag: float
    quelle: str
    kt_soll: str


class JahrReportResponse(BaseModel):
    jahr: int
    aktiven: GruppeOut
    passiven: GruppeOut
    ertrag: list[GruppeOut]
    aufwand: list[GruppeOut]
    ertrag_total: float
    aufwand_total: float
    gewinn: float
    bilanz_differenz: float
    abschreibungen: list[AbschreibungOut]
    abschreibungen_total: float
    checks: list[ExportCheck]
    blockers: int
    warnings: int
    ready: bool
    buchungen: int
    pdf_url: str
    paket_url: str


class YearListResponse(BaseModel):
    jahre: list[int] = Field(default_factory=list)
    aktuell: int
