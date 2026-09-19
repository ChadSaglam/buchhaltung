"""MWST-Abrechnung (B-67)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.export_batch import ExportCheck


class ZifferOut(BaseModel):
    ziffer: str
    label: str
    umsatz: float | None
    steuer: float | None
    rate: float | None


class MwstReportResponse(BaseModel):
    quartal: str  # JJJJ-Qn
    zeitraum: str  # "01.04.2026 – 30.06.2026"
    methode: Literal["effektiv", "saldo"]
    satz: float | None
    buchungen: int
    ready: bool
    blockers: int
    zu_bezahlen: float
    guthaben: float
    ziffern: list[ZifferOut]
    checks: list[ExportCheck]
    copy_block: str  # tab-separated, ready for the ePortal form


class QuarterListResponse(BaseModel):
    quartale: list[str]
    labels: dict[str, str]
    aktuell: str
