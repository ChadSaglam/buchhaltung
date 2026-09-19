"""Abgleich — which bank line paid which invoice (brainstorm phase 3).

Rules first, model later: a reference that matches is a fact, an amount that
matches inside a date window is a good guess, and a set of invoices that sums to
one Sammelauftrag is the case a human cannot do by hand. Every proposal carries
the *reason* in German — the user should read "Referenz stimmt exakt", never "0.93".

Pure module: dataclasses in, proposals out, no ORM and no I/O, so the whole
engine is unit-testable and can run in a worker thread.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date

from app.services.vendor_similarity import similarity

# Tier names double as the Match.tier column values.
TIER_REFERENCE = "referenz"
TIER_AMOUNT_DATE = "betrag_datum"
TIER_SUBSET = "sammelauftrag"

# An invoice is normally paid on or after its date; allow a little slack for
# statements that book a day earlier than the invoice is dated.
DAYS_BEFORE = 5
DAYS_AFTER = 40
# Two amounts are "the same" within half a Rappen.
CENT_TOLERANCE = 1
# A Sammelauftrag rarely bundles more than this many invoices; keeps the search cheap.
MAX_SUBSET_SIZE = 5
MAX_SUBSET_CANDIDATES = 18
MAX_SUBSET_SOLUTIONS = 4


def to_cents(amount: float | None) -> int:
    """Money as integer Rappen — subset sums must not drift (0.1 + 0.2 ≠ 0.3)."""
    return round(abs(float(amount or 0.0)) * 100)


@dataclass(frozen=True)
class DocumentRef:
    """An open document as the engine sees it."""

    id: int
    amount: float | None
    vendor: str = ""
    invoice_date: date | None = None
    due_date: date | None = None
    reference: str = ""

    @property
    def cents(self) -> int:
        return to_cents(self.amount)


@dataclass(frozen=True)
class TransactionRef:
    """An open bank line as the engine sees it. ``amount`` is signed (negative = paid out)."""

    id: int
    amount: float
    value_date: date | None = None
    description: str = ""
    reference: str = ""
    counterparty: str = ""

    @property
    def cents(self) -> int:
        return to_cents(self.amount)

    @property
    def is_debit(self) -> bool:
        return self.amount < 0

    @property
    def text(self) -> str:
        return f"{self.counterparty} {self.description}".strip()


@dataclass
class Proposal:
    """One proposed reconciliation: this transaction settles these documents."""

    transaction_id: int
    document_ids: list[int]
    tier: str
    score: float
    reason: str
    amounts: dict[int, float] = field(default_factory=dict)

    @property
    def is_split(self) -> bool:
        return len(self.document_ids) > 1


def _days_between(tx_date: date | None, doc_date: date | None) -> int | None:
    if tx_date is None or doc_date is None:
        return None
    return (tx_date - doc_date).days


def _in_window(tx: TransactionRef, doc: DocumentRef) -> bool:
    """True when the payment date is plausible for this invoice (or dates are unknown)."""
    delta = _days_between(tx.value_date, doc.invoice_date or doc.due_date)
    if delta is None:
        return True  # no date to contradict the amount
    return -DAYS_BEFORE <= delta <= DAYS_AFTER


def _date_phrase(tx: TransactionRef, doc: DocumentRef) -> str:
    delta = _days_between(tx.value_date, doc.invoice_date or doc.due_date)
    if delta is None:
        return "kein Datum zum Vergleichen"
    if delta == 0:
        return "am Rechnungsdatum"
    if delta > 0:
        return f"{delta} Tag{'e' if delta != 1 else ''} nach Rechnungsdatum"
    return f"{-delta} Tag{'e' if delta != -1 else ''} vor Rechnungsdatum"


def _vendor_score(tx: TransactionRef, doc: DocumentRef) -> float:
    """0..1 similarity between the invoice's vendor and whatever the bank printed."""
    if not doc.vendor or not tx.text:
        return 0.0
    whole = similarity(doc.vendor, tx.text)
    # A statement line often contains the vendor as one token among many
    # ("ZAHLUNG DEBITKARTE … ISO-Center AG"), so also try the best single word.
    tokens = [t for t in tx.text.split() if len(t) >= 4]
    best_token = max((similarity(doc.vendor, t) for t in tokens), default=0.0)
    return max(whole, best_token)


def _reference_matches(tx: TransactionRef, doc: DocumentRef) -> bool:
    a = (tx.reference or "").strip()
    b = (doc.reference or "").strip()
    return bool(a) and bool(b) and a == b


def _amounts_match(tx: TransactionRef, doc: DocumentRef) -> bool:
    return doc.cents > 0 and abs(tx.cents - doc.cents) <= CENT_TOLERANCE


def _single_proposals(tx: TransactionRef, docs: list[DocumentRef]) -> list[Proposal]:
    """Reference hits first (facts), then amount+date (good guesses)."""
    out: list[Proposal] = []
    for doc in docs:
        if _reference_matches(tx, doc):
            out.append(
                Proposal(
                    transaction_id=tx.id,
                    document_ids=[doc.id],
                    tier=TIER_REFERENCE,
                    score=1.0,
                    reason=f"Referenz stimmt exakt ({doc.reference})",
                    amounts={doc.id: round(doc.cents / 100, 2)},
                )
            )
    if out:
        return out

    for doc in docs:
        if not _amounts_match(tx, doc) or not _in_window(tx, doc):
            continue
        vendor = _vendor_score(tx, doc)
        # Amount alone is already strong; the vendor text can only add to it.
        score = round(min(0.95, 0.72 + 0.23 * vendor), 3)
        reason = f"Betrag exakt, {_date_phrase(tx, doc)}"
        if vendor >= 0.6:
            reason += f" · Text passt zu „{doc.vendor}“"
        out.append(
            Proposal(
                transaction_id=tx.id,
                document_ids=[doc.id],
                tier=TIER_AMOUNT_DATE,
                score=score,
                reason=reason,
                amounts={doc.id: round(doc.cents / 100, 2)},
            )
        )
    out.sort(key=lambda p: p.score, reverse=True)
    return out


def find_subsets(
    target_cents: int, candidates: list[DocumentRef], max_size: int = MAX_SUBSET_SIZE
) -> list[list[DocumentRef]]:
    """Every combination of ``candidates`` (size 2..max_size) summing to ``target_cents``.

    Exponential in theory; the candidate pool is capped and real Sammelaufträge
    bundle a handful of invoices, so the search stays in microseconds.
    """
    usable = [d for d in candidates if 0 < d.cents <= target_cents + CENT_TOLERANCE]
    usable.sort(key=lambda d: d.cents, reverse=True)
    usable = usable[:MAX_SUBSET_CANDIDATES]
    found: list[list[DocumentRef]] = []
    for size in range(2, min(max_size, len(usable)) + 1):
        for combo in itertools.combinations(usable, size):
            if abs(sum(d.cents for d in combo) - target_cents) <= CENT_TOLERANCE:
                found.append(list(combo))
                if len(found) >= MAX_SUBSET_SOLUTIONS:
                    return found
    return found


def _subset_proposal(tx: TransactionRef, docs: list[DocumentRef]) -> Proposal | None:
    """One Sammelauftrag → several invoices. Only for money leaving the account."""
    if not tx.is_debit or tx.cents <= 0:
        return None
    candidates = [d for d in docs if _in_window(tx, d)]
    subsets = find_subsets(tx.cents, candidates)
    if not subsets:
        return None

    # Prefer the combination whose vendors show up in the statement text, then the
    # smallest one — fewer invoices is the likelier bundle.
    def rank(subset: list[DocumentRef]) -> tuple[float, int]:
        return (-sum(_vendor_score(tx, d) for d in subset) / len(subset), len(subset))

    subsets.sort(key=rank)
    best = subsets[0]
    ambiguous = len(subsets) > 1
    score = 0.62 if ambiguous else 0.7
    reason = f"Summe von {len(best)} offenen Rechnungen ergibt genau diesen Betrag"
    if ambiguous:
        reason += f" · {len(subsets)} Kombinationen möglich, bitte prüfen"
    return Proposal(
        transaction_id=tx.id,
        document_ids=[d.id for d in best],
        tier=TIER_SUBSET,
        score=score,
        reason=reason,
        amounts={d.id: round(d.cents / 100, 2) for d in best},
    )


def propose_matches(
    transactions: list[TransactionRef],
    documents: list[DocumentRef],
    *,
    include_subsets: bool = True,
) -> list[Proposal]:
    """Best proposal per transaction; a document is never proposed twice.

    Transactions are processed strongest-evidence-first (reference, then exact
    amount, then bundles) so a confident line claims its invoice before a weaker
    one can take it.
    """
    open_docs = [d for d in documents if d.cents > 0]
    by_tx: dict[int, list[Proposal]] = {}
    for tx in transactions:
        singles = _single_proposals(tx, open_docs)
        subset = _subset_proposal(tx, open_docs) if include_subsets and not singles else None
        by_tx[tx.id] = singles + ([subset] if subset else [])

    order = sorted(
        transactions,
        key=lambda tx: (-(by_tx[tx.id][0].score if by_tx[tx.id] else 0.0), tx.id),
    )
    taken: set[int] = set()
    result: list[Proposal] = []
    for tx in order:
        for proposal in by_tx[tx.id]:
            if any(doc_id in taken for doc_id in proposal.document_ids):
                continue
            taken.update(proposal.document_ids)
            result.append(proposal)
            break
    result.sort(key=lambda p: (-p.score, p.transaction_id))
    return result
