"""Review-queue response schemas (B-59).

The queue is what the confidence threshold pushes to a human, so the shape the
UI reads is part of the contract, not an implementation detail.
"""

from __future__ import annotations

from pydantic import BaseModel


class ReviewItemOut(BaseModel):
    id: int
    beschreibung: str
    betrag: float
    predicted_soll: str
    predicted_haben: str
    predicted_mwst_code: str
    predicted_mwst_pct: str
    confidence: float
    source: str
    status: str
    created_at: str | None = None


class ReviewQueueResponse(BaseModel):
    threshold: float
    count: int
    items: list[ReviewItemOut]


class ReviewActionResponse(BaseModel):
    status: str
