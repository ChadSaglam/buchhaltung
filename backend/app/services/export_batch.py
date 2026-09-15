"""Banana batch hand-off (brainstorm 2026-09-13, phase 4).

An export is not a download, it is a *Buchungsperiode with a status*. Before the
file is written the bookings are checked (red/green, plain German); on export
they are stamped with the batch, so the next export offers only what is new and
downloading an old batch renders byte-identical content.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_transaction import TX_STATUS_OFFEN, BankTransaction
from app.models.booking import Booking
from app.models.document import STATUS_EXPORTIERT, STATUS_OFFEN, Document
from app.models.export_batch import FORMAT_BANANA, ExportBatch
from app.models.tenant import Tenant
from app.models.user import User
from app.services.classifier import vat_code_for
from app.services.documents import parse_date
from app.services.export import bookings_to_df, df_to_banana_tsv, fmt_swiss, round_chf

logger = logging.getLogger(__name__)

SEVERITY_BLOCKER = "blocker"
SEVERITY_WARNUNG = "warnung"

MAX_BATCH_ROWS = 5000


@dataclass
class Check:
    """One line of the pre-export checklist — green when ``count`` is 0."""

    code: str
    label: str
    detail: str
    severity: str
    count: int = 0
    booking_ids: list[int] = field(default_factory=list)


@dataclass
class Preflight:
    exportable: int
    total: float
    period_from: date | None
    period_to: date | None
    checks: list[Check]

    @property
    def blockers(self) -> int:
        return sum(1 for c in self.checks if c.severity == SEVERITY_BLOCKER and c.count)

    @property
    def ready(self) -> bool:
        return self.exportable > 0 and self.blockers == 0


def vat_disagrees(booking: Booking) -> bool:
    """True when the booking's VAT rate and code cannot both be right.

    A wrong code costs money on every receipt (B-48), so this blocks the export.
    An empty or zero rate is not a claim about VAT and passes.
    """
    raw = (booking.mwst_pct or "").strip()
    if not raw:
        return False
    try:
        rate = abs(float(raw))
    except ValueError:
        return True
    if rate == 0:
        return False
    resolved = vat_code_for(rate, booking.mwst_code or "")
    if resolved is None:
        return True
    _, expected_code = resolved
    code = (booking.mwst_code or "").strip()
    return bool(code) and code != expected_code


def booking_dates(bookings: list[Booking]) -> list[date]:
    days = [parse_date(b.datum or "") for b in bookings]
    return sorted(d for d in days if d is not None)


def duplicate_ids(bookings: list[Booking]) -> list[int]:
    """Bookings that look like the same posting twice — same day, amount and accounts."""
    seen: dict[tuple, list[int]] = defaultdict(list)
    for b in bookings:
        key = (b.datum or "", round(float(b.betrag or 0.0), 2), b.kt_soll or "", b.kt_haben or "")
        seen[key].append(b.id)
    return sorted(i for ids in seen.values() if len(ids) > 1 for i in ids)


class ExportBatchService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    # ── reading ──────────────────────────────────────────────────────────────

    async def open_bookings(self) -> list[Booking]:
        """Everything reconciled and not yet exported — the next batch, in booking order."""
        rows = await self.db.execute(
            select(Booking)
            .where(Booking.tenant_id == self.tenant_id, Booking.export_batch_id.is_(None))
            .order_by(Booking.id)
        )
        return list(rows.scalars().all())

    async def preflight(self) -> Preflight:
        bookings = await self.open_bookings()
        missing_accounts = [b.id for b in bookings if not (b.kt_soll or "").strip() or not (b.kt_haben or "").strip()]
        no_amount = [b.id for b in bookings if round(float(b.betrag or 0.0), 2) == 0]
        bad_date = [b.id for b in bookings if parse_date(b.datum or "") is None]
        vat_broken = [b.id for b in bookings if vat_disagrees(b)]
        doubles = duplicate_ids(bookings)

        today = datetime.now(UTC).date()
        open_lines = int(
            (
                await self.db.execute(
                    select(func.count(BankTransaction.id)).where(
                        BankTransaction.tenant_id == self.tenant_id,
                        BankTransaction.status == TX_STATUS_OFFEN,
                    )
                )
            ).scalar()
            or 0
        )
        overdue = int(
            (
                await self.db.execute(
                    select(func.count(Document.id)).where(
                        Document.tenant_id == self.tenant_id,
                        Document.status == STATUS_OFFEN,
                        Document.due_date.is_not(None),
                        Document.due_date < today,
                    )
                )
            ).scalar()
            or 0
        )

        checks = [
            Check(
                code="konten_fehlen",
                label="Alle Buchungen haben Soll- und Habenkonto",
                detail="Ohne Konten kann Banana die Buchung nicht importieren.",
                severity=SEVERITY_BLOCKER,
                count=len(missing_accounts),
                booking_ids=missing_accounts[:20],
            ),
            Check(
                code="betrag_null",
                label="Kein Betrag ist 0.00",
                detail="Eine Buchung ohne Betrag ist immer ein Fehler.",
                severity=SEVERITY_BLOCKER,
                count=len(no_amount),
                booking_ids=no_amount[:20],
            ),
            Check(
                code="datum_fehlt",
                label="Alle Daten sind lesbar",
                detail="Das Datum muss als Tag.Monat.Jahr vorliegen.",
                severity=SEVERITY_BLOCKER,
                count=len(bad_date),
                booking_ids=bad_date[:20],
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
                code="offene_bankzeilen",
                label="Keine offenen Bankzeilen",
                detail="Noch nicht abgeglichene Zeilen fehlen in diesem Export.",
                severity=SEVERITY_WARNUNG,
                count=open_lines,
            ),
            Check(
                code="ueberfaellige_dokumente",
                label="Keine überfälligen Rechnungen offen",
                detail="Fällige, noch nicht bezahlte Rechnungen sind nicht gebucht.",
                severity=SEVERITY_WARNUNG,
                count=overdue,
            ),
        ]
        days = booking_dates(bookings)
        return Preflight(
            exportable=len(bookings),
            total=float(round_chf(sum(float(b.betrag or 0.0) for b in bookings))),
            period_from=days[0] if days else None,
            period_to=days[-1] if days else None,
            checks=checks,
        )

    async def batches(self, limit: int = 50) -> list[ExportBatch]:
        rows = await self.db.execute(
            select(ExportBatch)
            .where(ExportBatch.tenant_id == self.tenant_id)
            .order_by(ExportBatch.id.desc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def batch(self, batch_id: int) -> ExportBatch:
        row = await self.db.execute(
            select(ExportBatch).where(ExportBatch.id == batch_id, ExportBatch.tenant_id == self.tenant_id)
        )
        batch = row.scalar_one_or_none()
        if batch is None:
            raise HTTPException(404, "Export nicht gefunden.")
        return batch

    async def bookings_of(self, batch_id: int) -> list[Booking]:
        rows = await self.db.execute(
            select(Booking)
            .where(Booking.tenant_id == self.tenant_id, Booking.export_batch_id == batch_id)
            .order_by(Booking.id)
        )
        return list(rows.scalars().all())

    # ── writing ──────────────────────────────────────────────────────────────

    async def create(self, note: str = "") -> ExportBatch:
        """Stamp everything that is ready and render the file once."""
        pre = await self.preflight()
        if pre.exportable == 0:
            raise HTTPException(404, "Keine neuen Buchungen zum Exportieren.")
        if pre.exportable > MAX_BATCH_ROWS:
            raise HTTPException(400, f"Zu viele Buchungen für einen Export (max {MAX_BATCH_ROWS}).")
        if pre.blockers:
            blocking = ", ".join(c.label for c in pre.checks if c.severity == SEVERITY_BLOCKER and c.count)
            raise HTTPException(409, f"Export nicht möglich — zuerst korrigieren: {blocking}.")

        bookings = await self.open_bookings()
        now = datetime.now(UTC)
        batch = ExportBatch(
            tenant_id=self.tenant_id,
            format=FORMAT_BANANA,
            booking_count=len(bookings),
            total_betrag=pre.total,
            total_mwst=float(round_chf(sum(float(b.mwst_amount or 0.0) for b in bookings))),
            period_from=pre.period_from,
            period_to=pre.period_to,
            note=note[:255],
            created_by=self.user.id,
        )
        self.db.add(batch)
        await self.db.flush()

        for booking in bookings:
            booking.export_batch_id = batch.id
            booking.exported_at = now

        # A document whose booking just left is handed over — that is its final state.
        booking_ids = [b.id for b in bookings]
        if booking_ids:
            docs = await self.db.execute(
                select(Document).where(Document.tenant_id == self.tenant_id, Document.booking_id.in_(booking_ids))
            )
            for doc in docs.scalars().all():
                doc.status = STATUS_EXPORTIERT

        content = render_banana(bookings)
        batch.filename = f"banana_{now.date().isoformat()}_{batch.id}.txt"
        batch.checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        await self.db.flush()
        logger.info(
            "export batch %s created: %s bookings, total %s",
            batch.id,
            batch.booking_count,
            batch.total_betrag,
        )
        return batch

    async def content(self, batch_id: int) -> tuple[ExportBatch, str]:
        """Re-render a batch — same bookings, same bytes as when it was created."""
        batch = await self.batch(batch_id)
        return batch, render_banana(await self.bookings_of(batch_id))

    async def cover_sheet(self, batch_id: int) -> tuple[ExportBatch, str]:
        batch = await self.batch(batch_id)
        bookings = await self.bookings_of(batch_id)
        tenant = (await self.db.execute(select(Tenant).where(Tenant.id == self.tenant_id))).scalar_one_or_none()
        return batch, render_cover_sheet(batch, bookings, company=getattr(tenant, "name", "") or "")


def render_banana(bookings: list[Booking]) -> str:
    """The Banana import file for these bookings (pure — the checksum depends on it)."""
    return df_to_banana_tsv(bookings_to_df(bookings))


def _swiss_day(day: date | None) -> str:
    return day.strftime("%d.%m.%Y") if day else "—"


def render_cover_sheet(batch: ExportBatch, bookings: list[Booking], *, company: str = "") -> str:
    """The sheet that travels with the file, so a Treuhänder sees what they got."""
    per_account: dict[str, list[float]] = defaultdict(list)
    for b in bookings:
        per_account[(b.kt_soll or "—").strip()].append(float(b.betrag or 0.0))

    lines = [
        "Banana-Import — Deckblatt",
        "=" * 40,
        f"Firma:        {company or '—'}",
        f"Export:       #{batch.id}",
        f"Erstellt:     {batch.created_at.strftime('%d.%m.%Y %H:%M') if batch.created_at else '—'}",
        f"Zeitraum:     {_swiss_day(batch.period_from)} – {_swiss_day(batch.period_to)}",
        f"Buchungen:    {batch.booking_count}",
        f"Total:        CHF {fmt_swiss(batch.total_betrag)}",
        f"davon MwSt:   CHF {fmt_swiss(batch.total_mwst)}",
        f"Datei:        {batch.filename}",
        f"Prüfsumme:    {batch.checksum}",
        "",
        "Sollkonten",
        "-" * 40,
    ]
    for account in sorted(per_account):
        amounts = per_account[account]
        lines.append(f"{account:<10} {len(amounts):>4} Buchung(en)   CHF {fmt_swiss(sum(amounts)):>14}")
    lines += [
        "",
        "Import in Banana",
        "-" * 40,
        "Aktionen → Import in Buchhaltung → Text-Datei mit Spaltenüberschriften.",
        "Diese Buchungen sind als exportiert markiert; der nächste Export enthält",
        "sie nicht mehr. Dieselbe Datei kann jederzeit erneut heruntergeladen werden.",
    ]
    if batch.note:
        lines += ["", f"Notiz: {batch.note}"]
    return "\n".join(lines) + "\n"
