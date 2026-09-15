"""Abgleich (phase 3) — bank lines, proposals, decisions."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentOut


class BankTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    value_date: date | None
    description: str
    amount: float
    currency: str
    reference: str
    counterparty: str
    source: str
    booking_id: int | None
    created_at: datetime | None


class MatchedDocument(BaseModel):
    """A document inside a proposal, with the part of the line that settles it."""

    document: DocumentOut
    match_id: int
    amount: float


class AbgleichItem(BaseModel):
    """One decision for the user: this bank line settles these documents, for this reason."""

    transaction: BankTransactionOut
    documents: list[MatchedDocument]
    tier: str
    score: float
    reason: str
    is_split: bool


class AbgleichSummary(BaseModel):
    vorschlaege: int
    offene_zeilen: int
    offene_dokumente: int
    exakt: int  # proposals resting on a reference — no judgement needed


class AbgleichResponse(BaseModel):
    items: list[AbgleichItem]
    open_transactions: list[BankTransactionOut]
    open_documents: list[DocumentOut]
    summary: AbgleichSummary


class StatementImportResponse(BaseModel):
    imported: int
    duplicates: int
    proposals: int


class ManualMatchRequest(BaseModel):
    document_ids: list[int] = Field(min_length=1, max_length=20)


class DecisionResponse(BaseModel):
    transaction_id: int
    status: str
    bookings: list[int] = []
    documents: list[int] = []
