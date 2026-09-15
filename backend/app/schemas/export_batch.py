"""Banana batch export (phase 4) — checklist, batches, hand-off metadata."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExportCheck(BaseModel):
    code: str
    label: str
    detail: str
    severity: str  # blocker | warnung
    count: int
    booking_ids: list[int] = []


class PreflightResponse(BaseModel):
    exportable: int
    total: float
    period_from: date | None
    period_to: date | None
    ready: bool
    blockers: int
    checks: list[ExportCheck]


class ExportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    format: str
    filename: str
    booking_count: int
    total_betrag: float
    total_mwst: float
    period_from: date | None
    period_to: date | None
    checksum: str
    note: str
    created_at: datetime | None


class ExportBatchListResponse(BaseModel):
    items: list[ExportBatchOut]
    count: int


class CreateBatchRequest(BaseModel):
    note: str = Field("", max_length=255)
