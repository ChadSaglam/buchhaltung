"""Abgleich — persist bank lines, keep proposals fresh, turn a confirmation into bookings.

The engine (`services/matching.py`) stays pure; this module is the part that
touches the database: it feeds the engine, stores its proposals as `matches`
rows, and on confirmation writes the bookings the customer would have typed by
hand — one per document, dated on the bank line, against the document's accounts.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_transaction import (
    TX_STATUS_GEBUCHT,
    TX_STATUS_OFFEN,
    TX_STATUS_ZUGEORDNET,
    BankTransaction,
)
from app.models.booking import Booking
from app.models.document import STATUS_BEZAHLT, STATUS_OFFEN, Document
from app.models.match import (
    MATCH_ABGELEHNT,
    MATCH_BESTAETIGT,
    MATCH_VORGESCHLAGEN,
    TIER_MANUAL,
    Match,
)
from app.models.user import User
from app.services.classifier import TenantClassifier, calc_mwst
from app.services.documents import parse_date
from app.services.matching import DocumentRef, Proposal, TransactionRef, propose_matches

logger = logging.getLogger(__name__)


def dedup_key(tenant_id: int, *, day: date | None, amount: float, description: str) -> str:
    """Same statement line uploaded twice → same key, so the unique index rejects the copy."""
    raw = f"{tenant_id}|{day.isoformat() if day else ''}|{round(float(amount), 2):.2f}|{' '.join(description.split()).lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def signed_amount(row: dict) -> float:
    """Parser rows carry Belastung/Gutschrift; the model stores one signed amount."""
    credit = row.get("Gutschrift")
    if credit:
        return round(abs(float(credit)), 2)
    debit = row.get("Belastung")
    if debit:
        return -round(abs(float(debit)), 2)
    return -round(abs(float(row.get("Betrag CHF") or 0)), 2)


@dataclass
class ImportResult:
    imported: int
    duplicates: int
    transaction_ids: list[int]


class AbgleichService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    # ── intake ───────────────────────────────────────────────────────────────

    async def import_rows(self, rows: list[dict], *, statement_key: str = "", source: str = "pdf") -> ImportResult:
        """Persist parsed statement rows; rows already stored are counted, not duplicated."""
        existing = set(
            (
                await self.db.execute(
                    select(BankTransaction.dedup_key).where(BankTransaction.tenant_id == self.tenant_id)
                )
            )
            .scalars()
            .all()
        )
        imported: list[BankTransaction] = []
        duplicates = 0
        for row in rows:
            day = parse_date(str(row.get("Datum") or ""))
            amount = signed_amount(row)
            description = " ".join(str(row.get("Beschreibung") or "").split())
            key = dedup_key(self.tenant_id, day=day, amount=amount, description=description)
            if key in existing:
                duplicates += 1
                continue
            existing.add(key)
            imported.append(
                BankTransaction(
                    tenant_id=self.tenant_id,
                    status=TX_STATUS_OFFEN,
                    value_date=day,
                    booking_date=day,
                    description=description,
                    amount=amount,
                    currency="CHF",
                    reference=str(row.get("Referenz") or "")[:27],
                    counterparty=str(row.get("Gegenpartei") or "")[:255],
                    statement_key=statement_key[:255],
                    dedup_key=key,
                    source=source,
                    uploaded_by=self.user.id,
                )
            )
        self.db.add_all(imported)
        await self.db.flush()
        return ImportResult(imported=len(imported), duplicates=duplicates, transaction_ids=[t.id for t in imported])

    # ── proposals ────────────────────────────────────────────────────────────

    async def open_transactions(self) -> list[BankTransaction]:
        rows = await self.db.execute(
            select(BankTransaction)
            .where(BankTransaction.tenant_id == self.tenant_id, BankTransaction.status == TX_STATUS_OFFEN)
            .order_by(BankTransaction.value_date, BankTransaction.id)
        )
        return list(rows.scalars().all())

    async def open_documents(self) -> list[Document]:
        rows = await self.db.execute(
            select(Document)
            .where(Document.tenant_id == self.tenant_id, Document.status == STATUS_OFFEN)
            .order_by(Document.id)
        )
        return list(rows.scalars().all())

    async def _decided_pairs(self) -> set[tuple[int, int]]:
        """Pairs the user already judged — never propose them again."""
        rows = await self.db.execute(
            select(Match.document_id, Match.transaction_id).where(
                Match.tenant_id == self.tenant_id, Match.status != MATCH_VORGESCHLAGEN
            )
        )
        return {(d, t) for d, t in rows.all()}

    async def refresh_proposals(self) -> list[Match]:
        """Re-run the engine and store its proposals. Old, untouched proposals are replaced."""
        transactions = await self.open_transactions()
        documents = await self.open_documents()
        decided = await self._decided_pairs()

        tx_refs = [
            TransactionRef(
                id=t.id,
                amount=float(t.amount or 0.0),
                value_date=t.value_date,
                description=t.description or "",
                reference=t.reference or "",
                counterparty=t.counterparty or "",
            )
            for t in transactions
        ]
        doc_refs = [
            DocumentRef(
                id=d.id,
                amount=d.amount,
                vendor=d.vendor or "",
                invoice_date=d.invoice_date,
                due_date=d.due_date,
                reference=d.qr_reference or "",
            )
            for d in documents
        ]
        # CPU-bound combinatorics on a large month; keep the loop free (B-49).
        proposals: list[Proposal] = await asyncio.to_thread(propose_matches, tx_refs, doc_refs)
        proposals = [
            p for p in proposals if not any((doc_id, p.transaction_id) in decided for doc_id in p.document_ids)
        ]

        await self.db.execute(
            delete(Match).where(Match.tenant_id == self.tenant_id, Match.status == MATCH_VORGESCHLAGEN)
        )
        rows: list[Match] = []
        for proposal in proposals:
            for doc_id in proposal.document_ids:
                rows.append(
                    Match(
                        tenant_id=self.tenant_id,
                        document_id=doc_id,
                        transaction_id=proposal.transaction_id,
                        status=MATCH_VORGESCHLAGEN,
                        tier=proposal.tier,
                        score=proposal.score,
                        reason=proposal.reason[:255],
                        amount=proposal.amounts.get(doc_id, 0.0),
                    )
                )
        self.db.add_all(rows)
        await self.db.flush()
        return rows

    async def proposals(self) -> list[Match]:
        rows = await self.db.execute(
            select(Match)
            .where(Match.tenant_id == self.tenant_id, Match.status == MATCH_VORGESCHLAGEN)
            .order_by(Match.score.desc(), Match.transaction_id, Match.document_id)
        )
        return list(rows.scalars().all())

    # ── decisions ────────────────────────────────────────────────────────────

    async def _own_transaction(self, transaction_id: int) -> BankTransaction:
        row = await self.db.execute(
            select(BankTransaction).where(
                BankTransaction.id == transaction_id, BankTransaction.tenant_id == self.tenant_id
            )
        )
        tx = row.scalar_one_or_none()
        if tx is None:
            raise HTTPException(404, "Bankzeile nicht gefunden.")
        return tx

    async def _own_document(self, document_id: int) -> Document:
        row = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == self.tenant_id)
        )
        doc = row.scalar_one_or_none()
        if doc is None:
            raise HTTPException(404, "Dokument nicht gefunden.")
        return doc

    async def _group(self, transaction_id: int) -> list[Match]:
        """A Sammelauftrag is several match rows on one transaction — they are decided together."""
        rows = await self.db.execute(
            select(Match).where(
                Match.tenant_id == self.tenant_id,
                Match.transaction_id == transaction_id,
                Match.status == MATCH_VORGESCHLAGEN,
            )
        )
        return list(rows.scalars().all())

    async def confirm(self, transaction_id: int) -> list[Booking]:
        """Book what the user just confirmed: one booking per document, on the bank line's date."""
        group = await self._group(transaction_id)
        if not group:
            raise HTTPException(404, "Kein Vorschlag zu dieser Bankzeile.")
        tx = await self._own_transaction(transaction_id)
        now = datetime.now(UTC)
        classifier = TenantClassifier(self.tenant_id, self.db)
        bookings: list[Booking] = []

        for match in group:
            doc = await self._own_document(match.document_id)
            amount = round(float(match.amount or doc.amount or 0.0), 2)
            booking = Booking(
                tenant_id=self.tenant_id,
                datum=tx.value_date.strftime("%d.%m.%Y") if tx.value_date else "",
                beschreibung=" ".join(p for p in (doc.vendor, doc.invoice_no) if p).strip() or doc.filename,
                betrag=amount,
                kt_soll=doc.kt_soll,
                kt_haben=doc.kt_haben,
                mwst_code=doc.mwst_code,
                mwst_pct=doc.mwst_pct,
                mwst_amount=float(calc_mwst(amount, doc.mwst_pct) or 0.0),
                rechnung=doc.invoice_no,
                source="abgleich",
                source_key=doc.file_key,
            )
            self.db.add(booking)
            await self.db.flush()
            bookings.append(booking)

            doc.status = STATUS_BEZAHLT
            doc.booking_id = booking.id
            match.status = MATCH_BESTAETIGT
            match.decided_by = self.user.id
            match.decided_at = now
            # The user just confirmed this vendor → account pairing; that is the learning.
            if doc.vendor and doc.kt_soll:
                await classifier.save_to_memory(doc.vendor, doc.kt_soll, doc.kt_haben, doc.mwst_code, doc.mwst_pct)

        tx.status = TX_STATUS_GEBUCHT if len(bookings) == 1 else TX_STATUS_ZUGEORDNET
        tx.booking_id = bookings[0].id if len(bookings) == 1 else None
        await self.db.flush()
        return bookings

    async def reject(self, transaction_id: int) -> int:
        """The proposal was wrong. Remember the decision so it is never proposed again."""
        group = await self._group(transaction_id)
        if not group:
            raise HTTPException(404, "Kein Vorschlag zu dieser Bankzeile.")
        now = datetime.now(UTC)
        for match in group:
            match.status = MATCH_ABGELEHNT
            match.decided_by = self.user.id
            match.decided_at = now
        await self.db.flush()
        return len(group)

    async def manual(self, transaction_id: int, document_ids: list[int]) -> list[Booking]:
        """The engine had nothing (or was wrong) — the user picks the invoices themselves."""
        if not document_ids:
            raise HTTPException(400, "Mindestens ein Dokument auswählen.")
        tx = await self._own_transaction(transaction_id)
        await self.db.execute(
            delete(Match).where(
                Match.tenant_id == self.tenant_id,
                Match.transaction_id == transaction_id,
                Match.status == MATCH_VORGESCHLAGEN,
            )
        )
        for document_id in dict.fromkeys(document_ids):
            doc = await self._own_document(document_id)
            if doc.status != STATUS_OFFEN:
                raise HTTPException(409, f"Dokument {document_id} ist nicht mehr offen.")
            self.db.add(
                Match(
                    tenant_id=self.tenant_id,
                    document_id=document_id,
                    transaction_id=tx.id,
                    status=MATCH_VORGESCHLAGEN,
                    tier=TIER_MANUAL,
                    score=1.0,
                    reason="Manuell zugeordnet",
                    amount=round(float(doc.amount or 0.0), 2),
                )
            )
        await self.db.flush()
        return await self.confirm(tx.id)

    async def ignore_transaction(self, transaction_id: int) -> BankTransaction:
        """Not an invoice payment (bank fee, own transfer) — take it out of the inbox."""
        from app.models.bank_transaction import TX_STATUS_IGNORIERT

        tx = await self._own_transaction(transaction_id)
        tx.status = TX_STATUS_IGNORIERT
        await self.db.execute(
            delete(Match).where(
                Match.tenant_id == self.tenant_id,
                Match.transaction_id == transaction_id,
                Match.status == MATCH_VORGESCHLAGEN,
            )
        )
        await self.db.flush()
        return tx
