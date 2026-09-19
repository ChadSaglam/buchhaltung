"""Monatsabschluss-Check (B-66)."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.export_batch import ExportCheck


class MonthKpisOut(BaseModel):
    buchungen: int
    einnahmen: float
    ausgaben: float
    bank_bewegung: float
    konto_1020_bewegung: float
    differenz: float


class MonthReportResponse(BaseModel):
    monat: str  # JJJJ-MM
    label: str  # "April 2026"
    ready: bool
    blockers: int
    warnings: int
    kpis: MonthKpisOut
    checks: list[ExportCheck]


class MonthListResponse(BaseModel):
    """Every month that has data, newest first — the picker needs no configuration."""

    monate: list[str]
    labels: dict[str, str]
    aktuell: str
