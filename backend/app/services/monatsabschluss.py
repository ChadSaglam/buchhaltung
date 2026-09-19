"""Monatsabschluss-Check (B-66).

One page, red or green, nothing to configure: is this month closed, or what is
still missing? Everything is derived from what the tenant already has — bank
lines, bookings, documents — so the check works on the first day a customer
uses the app, with no opening balances to enter.

The money question is the movement, not the balance: what moved through the
bank in the month must equal what moved through account 1020 in the bookings.
A balance check would need an opening balance nobody has typed in; a movement
check needs nothing and catches the same mistakes (a missing booking, a wrong
account, a line booked twice).
"""

from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_transaction import (
    TX_STATUS_IGNORIERT,
    TX_STATUS_OFFEN,
    TX_STATUS_ZUGEORDNET,
    BankTransaction,
)
from app.models.booking import Booking
from app.models.document import STATUS_OFFEN, Document
from app.models.user import User
from app.services.documents import parse_date
from app.services.export import fmt_swiss, round_chf
from app.services.export_batch import (
    SEVERITY_BLOCKER,
    SEVERITY_WARNUNG,
    Check,
    duplicate_ids,
    vat_disagrees,
)
from app.services.offene_posten import effective_due_date

logger = logging.getLogger(__name__)

BANK_ACCOUNT = "1020"
# A difference below one Rappen is rounding, not a mistake.
TOLERANCE = 0.005

MONTH_NAMES = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)


def month_bounds(monat: str) -> tuple[date, date]:
    """'2026-04' → (1.4.2026, 30.4.2026); anything else is a 400."""
    try:
        year_text, month_text = monat.split("-")
        year, month = int(year_text), int(month_text)
        first = date(year, month, 1)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(400, "Monat im Format JJJJ-MM angeben, z. B. 2026-04.") from exc
    return first, date(year, month, calendar.monthrange(year, month)[1])


def month_label(monat: str) -> str:
    first, _ = month_bounds(monat)
    return f"{MONTH_NAMES[first.month - 1]} {first.year}"


def month_key(day: date | None) -> str | None:
    return f"{day.year:04d}-{day.month:02d}" if day else None


def signed_bank_effect(booking: Booking) -> float:
    """How this booking moved the bank account: + into 1020, − out of it."""
    amount = float(booking.betrag or 0.0)
    soll = (booking.kt_soll or "").strip()
    haben = (booking.kt_haben or "").strip()
    if soll == BANK_ACCOUNT and haben == BANK_ACCOUNT:
        return 0.0
    if soll == BANK_ACCOUNT:
        return amount
    if haben == BANK_ACCOUNT:
        return -amount
    return 0.0


def is_revenue(booking: Booking) -> bool:
    """Swiss KMU chart: 3xxx…4xxx on the credit side is revenue."""
    haben = (booking.kt_haben or "").strip()
    return haben.startswith("3")


def is_expense(booking: Booking) -> bool:
    soll = (booking.kt_soll or "").strip()
    return soll[:1] in {"4", "5", "6"}


@dataclass
class MonthKpis:
    buchungen: int
    einnahmen: float
    ausgaben: float
    bank_bewegung: float
    konto_1020_bewegung: float
    differenz: float


@dataclass
class MonthReport:
    monat: str
    label: str
    kpis: MonthKpis
    checks: list[Check] = field(default_factory=list)

    @property
    def blockers(self) -> int:
        return sum(1 for c in self.checks if c.severity == SEVERITY_BLOCKER and c.count)

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.severity == SEVERITY_WARNUNG and c.count)

    @property
    def ready(self) -> bool:
        """Green means: nothing blocks this month being called closed."""
        return self.blockers == 0


def default_month(days: list[date], today: date | None = None) -> str:
    """The month the user most likely wants: the newest one with data, else this one."""
    now = today or datetime.now(UTC).date()
    if not days:
        return f"{now.year:04d}-{now.month:02d}"
    newest = max(days)
    return f"{newest.year:04d}-{newest.month:02d}"


class MonatsabschlussService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    async def _bookings(self) -> list[Booking]:
        rows = await self.db.execute(select(Booking).where(Booking.tenant_id == self.tenant_id).order_by(Booking.id))
        return list(rows.scalars().all())

    async def _transactions(self) -> list[BankTransaction]:
        rows = await self.db.execute(
            select(BankTransaction).where(BankTransaction.tenant_id == self.tenant_id).order_by(BankTransaction.id)
        )
        return list(rows.scalars().all())

    async def _open_documents(self) -> list[Document]:
        rows = await self.db.execute(
            select(Document).where(Document.tenant_id == self.tenant_id, Document.status == STATUS_OFFEN)
        )
        return list(rows.scalars().all())

    async def months(self) -> list[str]:
        """Every month that has a booking or a bank line, newest first."""
        keys: set[str] = set()
        for booking in await self._bookings():
            key = month_key(parse_date(booking.datum or ""))
            if key:
                keys.add(key)
        for tx in await self._transactions():
            key = month_key(tx.value_date or tx.booking_date)
            if key:
                keys.add(key)
        return sorted(keys, reverse=True)

    async def report(self, monat: str | None = None, today: date | None = None) -> MonthReport:
        first, last = month_bounds(monat) if monat else month_bounds(default_month(await self._month_days(), today))
        key = f"{first.year:04d}-{first.month:02d}"

        bookings = [b for b in await self._bookings() if month_key(parse_date(b.datum or "")) == key]
        transactions = [t for t in await self._transactions() if month_key(t.value_date or t.booking_date) == key]
        documents = await self._open_documents()

        bank_movement = float(
            round_chf(sum(float(t.amount or 0.0) for t in transactions if t.status != TX_STATUS_IGNORIERT))
        )
        account_movement = float(round_chf(sum(signed_bank_effect(b) for b in bookings)))
        difference = float(round_chf(bank_movement - account_movement))

        kpis = MonthKpis(
            buchungen=len(bookings),
            einnahmen=float(round_chf(sum(float(b.betrag or 0.0) for b in bookings if is_revenue(b)))),
            ausgaben=float(round_chf(sum(float(b.betrag or 0.0) for b in bookings if is_expense(b)))),
            bank_bewegung=bank_movement,
            konto_1020_bewegung=account_movement,
            differenz=difference,
        )

        unmatched = [t.id for t in transactions if t.status in (TX_STATUS_OFFEN, TX_STATUS_ZUGEORDNET)]
        no_receipt = [b.id for b in bookings if not (b.source_key or "").strip()]
        vat_broken = [b.id for b in bookings if vat_disagrees(b)]
        doubles = duplicate_ids(bookings)
        not_exported = [b.id for b in bookings if b.export_batch_id is None]
        overdue = [d.id for d in documents if (due := effective_due_date(d)) is not None and due <= last]

        checks = [
            Check(
                code="bank_stimmt",
                label="Bankbewegung stimmt mit Konto 1020",
                detail=(
                    "Stimmt."
                    if abs(difference) <= TOLERANCE
                    else f"Differenz CHF {fmt_swiss(difference)} — Bank {fmt_swiss(bank_movement)}, "
                    f"Konto 1020 {fmt_swiss(account_movement)}."
                ),
                severity=SEVERITY_BLOCKER,
                count=0 if abs(difference) <= TOLERANCE else 1,
            ),
            Check(
                code="bankzeilen_offen",
                label="Alle Bankzeilen sind abgeglichen",
                detail="Offene Zeilen fehlen in der Buchhaltung — im Abgleich bestätigen.",
                severity=SEVERITY_BLOCKER,
                count=len(unmatched),
                booking_ids=unmatched[:20],
            ),
            Check(
                code="mwst_unstimmig",
                label="MwSt-Satz und MwSt-Code passen zusammen",
                detail="Ein falscher Code kostet bei jeder Rechnung Geld.",
                severity=SEVERITY_BLOCKER,
                count=len(vat_broken),
                booking_ids=vat_broken[:20],
            ),
            Check(
                code="moegliche_doppel",
                label="Keine doppelten Buchungen",
                detail="Gleiches Datum, gleicher Betrag, gleiche Konten — bitte kurz prüfen.",
                severity=SEVERITY_WARNUNG,
                count=len(doubles),
                booking_ids=doubles[:20],
            ),
            Check(
                code="beleg_fehlt",
                label="Jede Buchung hat einen Beleg",
                detail="Ohne Beleg fehlt der Nachweis — Belegpflicht (Art. 958f OR).",
                severity=SEVERITY_WARNUNG,
                count=len(no_receipt),
                booking_ids=no_receipt[:20],
            ),
            Check(
                code="dokumente_faellig",
                label="Keine fälligen Rechnungen offen",
                detail="Fällige, noch nicht bezahlte Rechnungen gehören in diesen Monat.",
                severity=SEVERITY_WARNUNG,
                count=len(overdue),
            ),
            Check(
                code="nicht_exportiert",
                label="Alles nach Banana übergeben",
                detail="Diese Buchungen sind noch in keinem Export-Stapel.",
                severity=SEVERITY_WARNUNG,
                count=len(not_exported),
                booking_ids=not_exported[:20],
            ),
        ]
        logger.info("monatsabschluss %s: %s bookings, difference %s", key, len(bookings), difference)
        return MonthReport(monat=key, label=month_label(key), kpis=kpis, checks=checks)

    async def _month_days(self) -> list[date]:
        days = [parse_date(b.datum or "") for b in await self._bookings()]
        days += [t.value_date or t.booking_date for t in await self._transactions()]
        return [d for d in days if d is not None]
