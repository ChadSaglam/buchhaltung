"""The Treuhänder hand-off pack (B-17).

One zip, one hand-off. Until now a hand-off was: download the Banana file, find
the receipts, remember which quarter it was, and answer the Treuhänder's
questions by e-mail for two weeks. Every piece of the answer already existed —
the batch, the TSV, the documents, the audit log — it just never left the
building together.

    00-LIESMICH.txt        what is in here, and what is *not*
    10-Uebersicht.pdf      the cover sheet, as a file rather than a web page
    20-Buchungen.txt       the Banana import, byte-identical to the batch
    30-Belege/             the receipt behind each booking, numbered to match
    40-Buchungen.csv       the same rows as a spreadsheet, for reading
    50-Protokoll.csv       who did what, over the batch's period

Three decisions that shape the rest:

**It is built from the batch, not from "now".** `ExportBatchService.content()`
re-renders the exact bytes that were exported, checksum included, so a pack made
three months later is the same hand-off. A pack that quietly includes bookings
added since would be worse than no pack.

**Receipts are numbered after the booking they belong to.** The Treuhänder's
question is always "what is behind line 47", so the file is `047-…`. A booking
with no receipt is not silently absent: it is listed by number in the README,
because that list is the actual review task.

**The pack is bounded.** Same reasoning as B-54 in the other direction: a tenant
with 4'000 scanned statements should get a refusal with a number in it, not a
2 GB download that dies at 94 %.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.document import Document
from app.models.export_batch import ExportBatch
from app.models.tenant import Tenant
from app.models.user import User
from app.services.export import fmt_swiss, round_chf, safe_text
from app.services.export_batch import ExportBatchService
from app.services.pdf_render import Column, Meta, PdfDoc, Row
from app.services.storage import StorageError, get_storage

logger = logging.getLogger(__name__)

MB = 1024 * 1024
#: The whole pack, uncompressed. A receipt-heavy year is ~200 MB; beyond this a
#: hand-off wants splitting by quarter, and saying so beats a failed download.
MAX_PACK_BYTES = 512 * MB
#: One receipt. Anything larger is a scan that should have been compressed.
MAX_BELEG_BYTES = 50 * MB

LIESMICH = "00-LIESMICH.txt"
UEBERSICHT = "10-Uebersicht.pdf"
BUCHUNGEN_TSV = "20-Buchungen.txt"
BELEGE_DIR = "30-Belege"
BUCHUNGEN_CSV = "40-Buchungen.csv"
PROTOKOLL_CSV = "50-Protokoll.csv"

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(text: str, fallback: str = "Beleg") -> str:
    """A filename that is the same on every operating system.

    Vendor names arrive from OCR, so they contain slashes, umlauts, colons and
    the occasional newline. Anything outside ``[A-Za-z0-9._-]`` collapses to a
    dash; a name that collapses to nothing becomes the fallback. No path
    separator survives this, which is also why it is the only thing that builds
    a member name.
    """
    cleaned = _UNSAFE.sub("-", (text or "").strip()).strip("-.")
    return cleaned[:80] or fallback


def beleg_name(index: int, doc: Document) -> str:
    """``047-Migros-Rechnung.pdf`` — sorts with the booking it belongs to."""
    stem = safe_name(doc.vendor or doc.filename or "Beleg")
    suffix = ""
    if "." in (doc.filename or ""):
        suffix = "." + safe_name(doc.filename.rsplit(".", 1)[-1], "bin").lower()
    return f"{BELEGE_DIR}/{index:03d}-{stem}{suffix}"


@dataclass
class PackZeile:
    """One booking, and whether a receipt travelled with it."""

    nummer: int
    booking: Booking
    document: Document | None = None
    beleg_pfad: str = ""
    fehler: str = ""


@dataclass
class PackInhalt:
    batch: ExportBatch
    zeilen: list[PackZeile] = field(default_factory=list)
    protokoll: list[AuditLog] = field(default_factory=list)
    firma: str = ""

    @property
    def mit_beleg(self) -> list[PackZeile]:
        return [z for z in self.zeilen if z.beleg_pfad]

    @property
    def ohne_beleg(self) -> list[PackZeile]:
        return [z for z in self.zeilen if not z.beleg_pfad and not z.fehler]

    @property
    def fehlend(self) -> list[PackZeile]:
        """A document exists but its file could not be read — the worst case,
        because it is the only one that is not visible from the booking alone."""
        return [z for z in self.zeilen if z.fehler]


class PackTooLarge(ValueError):
    def __init__(self, bytes_so_far: int):
        self.bytes_so_far = bytes_so_far
        super().__init__(
            f"Das Paket überschreitet {MAX_PACK_BYTES // MB} MB "
            f"({bytes_so_far // MB} MB bei Abbruch). Bitte quartalsweise exportieren."
        )


def _swiss(day: date | datetime | None) -> str:
    return day.strftime("%d.%m.%Y") if day else "—"


def liesmich(inhalt: PackInhalt) -> str:
    """The first file a Treuhänder opens. Says what is here and what is missing."""
    batch = inhalt.batch
    lines = [
        "Übergabe an die Treuhand",
        "=" * 40,
        f"Firma:      {inhalt.firma or '—'}",
        f"Export:     #{batch.id}",
        f"Zeitraum:   {_swiss(batch.period_from)} – {_swiss(batch.period_to)}",
        f"Buchungen:  {batch.booking_count}",
        f"Total:      CHF {fmt_swiss(batch.total_betrag)} (davon MwSt CHF {fmt_swiss(batch.total_mwst)})",
        f"Prüfsumme:  {batch.checksum}",
        "",
        "Inhalt",
        "-" * 40,
    ]
    breite = max(len(n) for n in (UEBERSICHT, BUCHUNGEN_TSV, BUCHUNGEN_CSV, PROTOKOLL_CSV, BELEGE_DIR + "/"))
    lines += [
        f"  {UEBERSICHT:<{breite}}  Deckblatt mit Summen je Konto",
        f"  {BUCHUNGEN_TSV:<{breite}}  Banana-Importdatei ({batch.filename or 'Banana'})",
        f"  {BUCHUNGEN_CSV:<{breite}}  dieselben Zeilen zum Lesen",
        f"  {BELEGE_DIR + '/':<{breite}}  die Belege, nummeriert wie die Buchungen",
        f"  {PROTOKOLL_CSV:<{breite}}  wer im Zeitraum was geändert hat",
        "",
        f"Belege vorhanden:  {len(inhalt.mit_beleg)} von {len(inhalt.zeilen)}",
    ]

    if inhalt.ohne_beleg:
        lines += [
            "",
            "Ohne Beleg — das ist die Liste, die geprüft werden muss",
            "-" * 40,
        ]
        lines += [
            f"  {z.nummer:03d}  {_swiss(_booking_date(z.booking))}  "
            f"CHF {fmt_swiss(z.booking.betrag)}  {(z.booking.beschreibung or '').strip()[:60]}"
            for z in inhalt.ohne_beleg
        ]

    if inhalt.fehlend:
        lines += [
            "",
            "Beleg erfasst, Datei nicht lesbar — bitte nachfordern",
            "-" * 40,
        ]
        lines += [f"  {z.nummer:03d}  {z.fehler}" for z in inhalt.fehlend]

    lines += [
        "",
        "Nicht enthalten",
        "-" * 40,
        "  * Eröffnungsbilanz — es gibt noch keine; die Bilanz weist die Differenz aus.",
        "  * Kontoauszüge der Bank als Originaldateien.",
        "  * Buchungen, die nach diesem Export erfasst wurden (sie kommen im nächsten Paket).",
        "",
        f"Erstellt am {_swiss(datetime.now())} aus Buchhaltung.",
    ]
    return "\n".join(lines) + "\n"


def _booking_date(booking: Booking) -> date | None:
    raw = (booking.datum or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _betrag(value) -> str:
    """``1800.00`` — a number a spreadsheet can add up.

    Not ``fmt_swiss``: a thousands separator makes the cell text, and the first
    thing anybody does with this file is select a column and look at the sum.
    The eye-friendly formatting belongs in the PDF and the README.
    """
    return "" if value in (None, "") else f"{float(round_chf(value)):.2f}"


def buchungen_csv(inhalt: PackInhalt) -> str:
    """The same rows, readable. Deliberately not the import file — a Treuhänder
    who opens the Banana TSV in Excel has already changed it.

    Every text field goes through ``safe_text`` (B-53): descriptions come out of
    OCR, and a vendor line beginning with ``=`` is a formula the moment this
    lands in Excel.
    """
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Nr", "Datum", "Beschreibung", "Soll", "Haben", "Betrag", "MwSt-Code", "MwSt", "Beleg"])
    for z in inhalt.zeilen:
        b = z.booking
        writer.writerow(
            [
                f"{z.nummer:03d}",
                safe_text(b.datum),
                safe_text(b.beschreibung),
                safe_text(b.kt_soll),
                safe_text(b.kt_haben),
                _betrag(b.betrag),
                safe_text(b.mwst_code),
                _betrag(b.mwst_amount) if b.mwst_amount else "",
                z.beleg_pfad.rsplit("/", 1)[-1] if z.beleg_pfad else "",
            ]
        )
    return out.getvalue()


def protokoll_csv(entries: list[AuditLog]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Zeitpunkt", "Aktion", "Objekt", "Objekt-Nr", "Benutzer"])
    for entry in entries:
        writer.writerow(
            [
                entry.created_at.strftime("%d.%m.%Y %H:%M") if entry.created_at else "",
                safe_text(entry.action),
                safe_text(entry.target_type),
                safe_text(entry.target_id),
                entry.actor_user_id if entry.actor_user_id is not None else "",
            ]
        )
    return out.getvalue()


def uebersicht_pdf(inhalt: PackInhalt) -> bytes:
    """The cover sheet as a file. The HTML one stays the browser preview."""
    batch = inhalt.batch
    doc = PdfDoc(
        Meta(
            title="Übergabe an die Treuhand",
            subtitle=f"Export #{batch.id}",
            company=inhalt.firma,
            period=f"{_swiss(batch.period_from)} – {_swiss(batch.period_to)}",
            footer=inhalt.firma,
        )
    )
    doc.keyvalue(
        [
            ("Buchungen", str(batch.booking_count)),
            ("Total", f"CHF {fmt_swiss(batch.total_betrag)}"),
            ("davon MwSt", f"CHF {fmt_swiss(batch.total_mwst)}"),
            ("Belege", f"{len(inhalt.mit_beleg)} von {len(inhalt.zeilen)}"),
            ("Importdatei", batch.filename or "—"),
            # In full: a shortened hash looks like a complete one that does not match.
            ("Prüfsumme", batch.checksum or "—"),
        ]
    )

    per_konto: dict[str, float] = {}
    for z in inhalt.zeilen:
        konto = (z.booking.kt_soll or "—").strip()
        per_konto[konto] = per_konto.get(konto, 0.0) + float(z.booking.betrag or 0.0)
    doc.section("Summen je Sollkonto")
    doc.table(
        [Column("Konto", 30.0, "L"), Column("Buchungen", 30.0, "R"), Column("CHF", 40.0, "R", money=True)],
        [
            Row([konto, str(sum(1 for z in inhalt.zeilen if (z.booking.kt_soll or "—").strip() == konto)), total])
            for konto, total in sorted(per_konto.items())
        ],
    )

    if inhalt.ohne_beleg:
        doc.section(
            "Ohne Beleg",
            "Diese Buchungen haben kein Dokument im Paket. Das ist die Liste, die geprüft werden muss.",
        )
        doc.table(
            [
                Column("Nr", 16.0, "L"),
                Column("Datum", 26.0, "L"),
                Column("Beschreibung", 90.0, "L"),
                Column("CHF", 30.0, "R", money=True),
            ],
            [
                Row(
                    [
                        f"{z.nummer:03d}",
                        z.booking.datum or "",
                        (z.booking.beschreibung or "")[:60],
                        float(z.booking.betrag or 0.0),
                    ]
                )
                for z in inhalt.ohne_beleg
            ],
        )
    return doc.output()


class TreuhandPackService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id
        self.batches = ExportBatchService(db, user)

    async def inhalt(self, batch_id: int) -> tuple[PackInhalt, str]:
        """Everything the pack needs, plus the exact TSV the batch exported."""
        batch, tsv = await self.batches.content(batch_id)
        bookings = await self.batches.bookings_of(batch_id)
        firma = await self.db.scalar(select(Tenant.name).where(Tenant.id == self.tenant_id)) or ""

        docs_by_booking: dict[int, Document] = {}
        if bookings:
            rows = await self.db.execute(
                select(Document).where(
                    Document.tenant_id == self.tenant_id,
                    Document.booking_id.in_([b.id for b in bookings]),
                )
            )
            for document in rows.scalars().all():
                if document.booking_id is not None:
                    docs_by_booking.setdefault(document.booking_id, document)

        zeilen = [
            PackZeile(nummer=index, booking=booking, document=docs_by_booking.get(booking.id))
            for index, booking in enumerate(bookings, start=1)
        ]

        protokoll: list[AuditLog] = []
        if batch.period_from and batch.period_to:
            rows = await self.db.execute(
                select(AuditLog)
                .where(
                    AuditLog.tenant_id == self.tenant_id,
                    AuditLog.created_at >= datetime.combine(batch.period_from, datetime.min.time()),
                )
                .order_by(AuditLog.created_at)
            )
            protokoll = list(rows.scalars().all())

        return PackInhalt(batch=batch, zeilen=zeilen, protokoll=protokoll, firma=firma), tsv

    async def build(self, batch_id: int) -> tuple[str, bytes]:
        """The zip. Raises ``PackTooLarge`` rather than returning half a hand-off."""
        inhalt, tsv = await self.inhalt(batch_id)
        storage = get_storage()

        buffer = io.BytesIO()
        written = 0
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            # Receipts first: they are what can fail, and failing before the
            # summary is written keeps the README honest about what is inside.
            for zeile in inhalt.zeilen:
                document = zeile.document
                if document is None or not document.file_key:
                    continue
                try:
                    data = storage.read(document.file_key)
                except (StorageError, FileNotFoundError, OSError) as exc:
                    zeile.fehler = f"{document.filename or document.file_key}: {type(exc).__name__}"
                    logger.warning("pack %s: %s", batch_id, zeile.fehler)
                    continue
                if len(data) > MAX_BELEG_BYTES:
                    zeile.fehler = f"{document.filename or document.file_key}: zu gross ({len(data) // MB} MB)"
                    continue
                written += len(data)
                if written > MAX_PACK_BYTES:
                    raise PackTooLarge(written)
                zeile.beleg_pfad = beleg_name(zeile.nummer, document)
                archive.writestr(zeile.beleg_pfad, data)

            archive.writestr(LIESMICH, liesmich(inhalt))
            archive.writestr(UEBERSICHT, uebersicht_pdf(inhalt))
            archive.writestr(BUCHUNGEN_TSV, tsv)
            archive.writestr(BUCHUNGEN_CSV, buchungen_csv(inhalt))
            archive.writestr(PROTOKOLL_CSV, protokoll_csv(inhalt.protokoll))

        name = f"Treuhand-{safe_name(inhalt.firma, 'Firma')}-{inhalt.batch.id:04d}.zip"
        logger.info(
            "pack %s built: %s bookings, %s receipts, %s bytes",
            batch_id,
            len(inhalt.zeilen),
            len(inhalt.mit_beleg),
            buffer.tell(),
        )
        return name, buffer.getvalue()
