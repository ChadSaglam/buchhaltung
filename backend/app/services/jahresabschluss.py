"""Jahresabschluss (B-70) — Bilanz, Erfolgsrechnung, Abschreibungen, ein Paket.

Das Ziel ist ein Satz: *nur noch unterschreiben*. Aus den Buchungen, die das
Jahr über entstanden sind, wird die Bilanz per 31.12., die Erfolgsrechnung des
Jahres, ein belegter Abschreibungsvorschlag und eine Prüfliste — dazu ein ZIP
mit PDF, Banana-Datei und allen Belegen.

Zwei Ehrlichkeiten stecken im Code:

* **Ohne Eröffnungsbilanz geht die Bilanz nicht auf.** Dieses System bucht ab
  dem Tag, an dem ein Kunde anfängt; Anfangsbestände hat niemand getippt. Die
  Differenz wird darum *ausgewiesen und erklärt*, nicht als Fehler verkauft.
* **Abschreibungssätze werden nachgeschlagen, nicht erfunden.** Die Sätze
  stammen aus dem ESTV-Merkblatt A/1995 (degressiv, vom Buchwert). Wo das
  Merkblatt nichts sagt, gibt es keinen Vorschlag, sondern einen Hinweis.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.document import STATUS_OFFEN, Document
from app.models.kontenplan import Konto
from app.models.tenant import Tenant
from app.models.user import User
from app.services.documents import parse_date
from app.services.export import fmt_swiss, round_chf
from app.services.export_batch import (
    SEVERITY_BLOCKER,
    SEVERITY_WARNUNG,
    Check,
    duplicate_ids,
    render_banana,
    vat_disagrees,
)
from app.services.pdf_render import CONTENT_WIDTH, Column, Meta, PdfDoc, Row, money_columns
from app.services.receipts import read_receipt

logger = logging.getLogger(__name__)

TOLERANCE = 0.005
ABSCHREIBUNGSKONTO = "6800"

# KMU-Kontenrahmen: die erste Ziffer sagt, wohin ein Konto gehört.
KLASSE_LABEL = {
    "1": "Aktiven",
    "2": "Passiven",
    "3": "Betriebsertrag",
    "4": "Material- und Warenaufwand",
    "5": "Personalaufwand",
    "6": "Übriger Betriebsaufwand",
    "7": "Betrieblicher Nebenerfolg",
    "8": "Ausserordentliches und Steuern",
}
ERTRAGSKLASSEN = ("3", "7")
AUFWANDKLASSEN = ("4", "5", "6", "8")

# ESTV-Merkblatt A/1995, Normalsätze degressiv vom Buchwert. Linear wäre die
# Hälfte ("Für Abschreibungen auf dem Anschaffungswert sind die genannten Sätze
# um die Hälfte zu reduzieren"). Nur Konten, für die das Merkblatt einen Satz
# nennt, stehen hier — der Rest bekommt bewusst keinen Vorschlag.
ESTV_QUELLE = "ESTV-Merkblatt A/1995, degressiv vom Buchwert"
ABSCHREIBUNGSSAETZE: tuple[tuple[str, str, float], ...] = (
    ("1500", "Maschinen und Apparate", 30.0),
    ("1510", "Mobiliar und Einrichtungen", 25.0),
    ("1520", "Büromaschinen, Informatik, Kommunikation", 40.0),
    ("1530", "Fahrzeuge", 40.0),
    ("1540", "Werkzeuge und Geräte", 45.0),
    ("1600", "Immobilien (Gebäude allein)", 4.0),
)
# Anlagekonten ohne belegten Satz: kein Vorschlag, aber ein Hinweis.
ANLAGE_PREFIXE = ("15", "16", "17")

KONTO_LABEL = {
    "1000": "Kasse",
    "1020": "Bank",
    "1100": "Forderungen aus Lieferungen und Leistungen (Debitoren)",
    "1170": "Vorsteuer Material, Waren, Dienstleistungen",
    "1171": "Vorsteuer Investitionen und übriger Betriebsaufwand",
    "1176": "Verrechnungssteuer",
    "2000": "Verbindlichkeiten aus Lieferungen und Leistungen (Kreditoren)",
    "2200": "Geschuldete MWST (Umsatzsteuer)",
    "2800": "Eigenkapital",
    "3000": "Produktionserlöse",
    "3200": "Handelserlöse",
    "3400": "Dienstleistungserlöse",
    "4000": "Materialaufwand",
    "5000": "Lohnaufwand",
    "5700": "Sozialversicherungsaufwand",
    "6000": "Mietaufwand",
    "6500": "Büromaterial und Verwaltung",
    "6510": "Telefon und Internet",
    "6570": "Informatikaufwand",
    "6800": "Abschreibungen",
    "8900": "Direkte Steuern",
}


def year_bounds(jahr: int) -> tuple[date, date]:
    return date(jahr, 1, 1), date(jahr, 12, 31)


def parse_year(value: str | int | None, fallback: int) -> int:
    if value in (None, ""):
        return fallback
    try:
        jahr = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "Jahr als vierstellige Zahl angeben, z. B. 2026.") from exc
    if not 1990 <= jahr <= 2100:
        raise HTTPException(400, "Jahr als vierstellige Zahl angeben, z. B. 2026.")
    return jahr


def klasse(konto: str) -> str:
    return (konto or "").strip()[:1]


def rate_for(konto: str) -> tuple[str, float] | None:
    """Der belegte Abschreibungssatz für ein Anlagekonto, oder None."""
    number = (konto or "").strip()
    for prefix, label, satz in ABSCHREIBUNGSSAETZE:
        if number.startswith(prefix):
            return label, satz
    return None


@dataclass
class Position:
    konto: str
    bezeichnung: str
    saldo: float


@dataclass
class Gruppe:
    key: str
    label: str
    positionen: list[Position] = field(default_factory=list)

    @property
    def total(self) -> float:
        return float(round_chf(sum(p.saldo for p in self.positionen)))


@dataclass
class Abschreibung:
    konto: str
    bezeichnung: str
    buchwert: float
    satz: float
    betrag: float
    quelle: str = ESTV_QUELLE
    kt_soll: str = ABSCHREIBUNGSKONTO


@dataclass
class JahrReport:
    jahr: int
    aktiven: Gruppe
    passiven: Gruppe
    ertrag: list[Gruppe]
    aufwand: list[Gruppe]
    abschreibungen: list[Abschreibung]
    checks: list[Check]
    buchungen: int
    company: str = ""

    @property
    def ertrag_total(self) -> float:
        return float(round_chf(sum(g.total for g in self.ertrag)))

    @property
    def aufwand_total(self) -> float:
        return float(round_chf(sum(g.total for g in self.aufwand)))

    @property
    def gewinn(self) -> float:
        return float(round_chf(self.ertrag_total - self.aufwand_total))

    @property
    def bilanz_differenz(self) -> float:
        """Aktiven - (Passiven + Gewinn). Ohne Eröffnungsbilanz ist das nie 0."""
        return float(round_chf(self.aktiven.total - self.passiven.total - self.gewinn))

    @property
    def blockers(self) -> int:
        return sum(1 for c in self.checks if c.severity == SEVERITY_BLOCKER and c.count)

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.severity == SEVERITY_WARNUNG and c.count)

    @property
    def ready(self) -> bool:
        return self.blockers == 0 and self.buchungen > 0


def _saldi(bookings: list[Booking]) -> dict[str, float]:
    """Soll-Saldo je Konto: was im Soll steht, minus was im Haben steht."""
    saldi: dict[str, float] = {}
    for booking in bookings:
        betrag = float(booking.betrag or 0.0)
        soll = (booking.kt_soll or "").strip()
        haben = (booking.kt_haben or "").strip()
        if soll:
            saldi[soll] = saldi.get(soll, 0.0) + betrag
        if haben:
            saldi[haben] = saldi.get(haben, 0.0) - betrag
    return {k: float(round_chf(v)) for k, v in saldi.items()}


def _positions(
    saldi: dict[str, float], klassen: tuple[str, ...], labels: dict[str, str], *, invert: bool
) -> list[Position]:
    out = [
        Position(
            konto=konto,
            bezeichnung=labels.get(konto) or KONTO_LABEL.get(konto, ""),
            saldo=float(round_chf(-saldo if invert else saldo)),
        )
        for konto, saldo in saldi.items()
        if klasse(konto) in klassen
    ]
    out = [p for p in out if abs(p.saldo) > TOLERANCE]
    out.sort(key=lambda p: p.konto)
    return out


class JahresabschlussService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    async def _bookings(self) -> list[Booking]:
        rows = await self.db.execute(select(Booking).where(Booking.tenant_id == self.tenant_id))
        return list(rows.scalars().all())

    async def _labels(self) -> dict[str, str]:
        rows = await self.db.execute(select(Konto).where(Konto.tenant_id == self.tenant_id))
        return {k.konto_nr: k.beschreibung for k in rows.scalars().all() if k.konto_nr}

    async def _documents(self) -> list[Document]:
        rows = await self.db.execute(select(Document).where(Document.tenant_id == self.tenant_id))
        return list(rows.scalars().all())

    async def _company(self) -> str:
        tenant = (await self.db.execute(select(Tenant).where(Tenant.id == self.tenant_id))).scalar_one_or_none()
        return getattr(tenant, "name", "") or ""

    async def years(self) -> list[int]:
        bookings = await self._bookings()
        years = {d.year for d in (parse_date(b.datum or "") for b in bookings) if d}
        return sorted(years, reverse=True)

    async def report(self, jahr: int | None = None, today: date | None = None) -> JahrReport:
        now = today or datetime.now(UTC).date()
        bookings = await self._bookings()
        dated = [(parse_date(b.datum or ""), b) for b in bookings]
        if jahr is None:
            years = sorted({d.year for d, _ in dated if d}, reverse=True)
            jahr = years[0] if years else now.year
        first, last = year_bounds(jahr)

        im_jahr = [b for d, b in dated if d and first <= d <= last]
        bis_ende = [b for d, b in dated if d and d <= last]
        labels = await self._labels()

        bilanz_saldi = _saldi(bis_ende)
        erfolg_saldi = _saldi(im_jahr)

        aktiven = Gruppe("aktiven", "Aktiven", _positions(bilanz_saldi, ("1",), labels, invert=False))
        passiven = Gruppe("passiven", "Passiven", _positions(bilanz_saldi, ("2",), labels, invert=True))
        ertrag = [
            Gruppe(k, KLASSE_LABEL[k], _positions(erfolg_saldi, (k,), labels, invert=True)) for k in ERTRAGSKLASSEN
        ]
        aufwand = [
            Gruppe(k, KLASSE_LABEL[k], _positions(erfolg_saldi, (k,), labels, invert=False)) for k in AUFWANDKLASSEN
        ]
        ertrag = [g for g in ertrag if g.positionen]
        aufwand = [g for g in aufwand if g.positionen]

        abschreibungen = self._abschreibungen(aktiven)
        report = JahrReport(
            jahr=jahr,
            aktiven=aktiven,
            passiven=passiven,
            ertrag=ertrag,
            aufwand=aufwand,
            abschreibungen=abschreibungen,
            checks=[],
            buchungen=len(im_jahr),
            company=await self._company(),
        )
        report.checks = self._checks(report, im_jahr, await self._documents(), last)
        logger.info(
            "jahresabschluss %s: %s Buchungen, Gewinn %s, Bilanzdifferenz %s",
            jahr,
            len(im_jahr),
            report.gewinn,
            report.bilanz_differenz,
        )
        return report

    def _abschreibungen(self, aktiven: Gruppe) -> list[Abschreibung]:
        out: list[Abschreibung] = []
        for position in aktiven.positionen:
            if not position.konto.startswith(ANLAGE_PREFIXE):
                continue
            if position.saldo <= TOLERANCE:
                continue
            found = rate_for(position.konto)
            if found is None:
                continue
            label, satz = found
            out.append(
                Abschreibung(
                    konto=position.konto,
                    bezeichnung=position.bezeichnung or label,
                    buchwert=position.saldo,
                    satz=satz,
                    betrag=float(round_chf(position.saldo * satz / 100)),
                )
            )
        return out

    def _checks(self, report: JahrReport, im_jahr: list[Booking], documents: list[Document], last: date) -> list[Check]:
        ohne_konto = [b.id for b in im_jahr if not (b.kt_soll or "").strip() or not (b.kt_haben or "").strip()]
        # B-89: paid at the till, so nothing is owed at the balance-sheet date.
        offene = [
            d
            for d in documents
            if d.status == STATUS_OFFEN and not d.paid_at_source and d.invoice_date and d.invoice_date <= last
        ]
        nicht_exportiert = [b.id for b in im_jahr if b.export_batch_id is None]
        doppelte = duplicate_ids(im_jahr)
        mwst_streit = [b.id for b in im_jahr if vat_disagrees(b)]
        anlagen_ohne_satz = [
            p.konto
            for p in report.aktiven.positionen
            if p.konto.startswith(ANLAGE_PREFIXE) and p.saldo > TOLERANCE and rate_for(p.konto) is None
        ]
        abschreibung_gebucht = any((b.kt_soll or "").startswith("68") for b in im_jahr)
        differenz = abs(report.bilanz_differenz)

        return [
            Check(
                code="konto_fehlt",
                label="Jede Buchung hat Soll- und Habenkonto",
                detail="Ohne Konto taucht der Betrag weder in der Bilanz noch in der Erfolgsrechnung auf.",
                severity=SEVERITY_BLOCKER,
                count=len(ohne_konto),
                booking_ids=ohne_konto[:50],
            ),
            Check(
                code="offene_posten",
                label="Keine offenen Rechnungen per 31.12.",
                detail=(
                    f"{len(offene)} Rechnung(en) sind am Jahresende noch offen. Sie gehören als Debitoren "
                    "bzw. Kreditoren in die Bilanz — sonst fehlt der Gewinn des Jahres."
                    if offene
                    else "Alles bezahlt oder abgegrenzt."
                ),
                severity=SEVERITY_WARNUNG,
                count=len(offene),
            ),
            Check(
                code="abschreibungen",
                label="Abschreibungen sind gebucht",
                detail=(
                    "Es gibt Anlagevermögen, aber keine Buchung auf ein 68er-Konto. Der Vorschlag unten "
                    "folgt dem ESTV-Merkblatt A/1995."
                    if report.abschreibungen and not abschreibung_gebucht
                    else "Nichts abzuschreiben oder bereits gebucht."
                ),
                severity=SEVERITY_WARNUNG,
                count=len(report.abschreibungen) if not abschreibung_gebucht else 0,
            ),
            Check(
                code="anlagen_ohne_satz",
                label="Für jedes Anlagekonto gibt es einen belegten Satz",
                detail=(
                    f"Kein Satz im Merkblatt A/1995 für: {', '.join(anlagen_ohne_satz)}. "
                    "Hier entscheidet der Treuhänder, wir raten nicht."
                    if anlagen_ohne_satz
                    else "Alle Anlagekonten haben einen belegten Satz."
                ),
                severity=SEVERITY_WARNUNG,
                count=len(anlagen_ohne_satz),
            ),
            Check(
                code="bilanz_differenz",
                label="Bilanz geht auf",
                detail=(
                    f"Aktiven minus Passiven und Gewinn ergibt CHF {fmt_swiss(report.bilanz_differenz)}. "
                    "Das ist normal, solange keine Eröffnungsbilanz erfasst ist: dieses System bucht ab dem "
                    "ersten Beleg, Anfangsbestände kennt es nicht. Der Treuhänder trägt sie einmal nach."
                    if differenz > TOLERANCE
                    else "Aktiven = Passiven + Gewinn."
                ),
                severity=SEVERITY_WARNUNG,
                count=1 if differenz > TOLERANCE else 0,
            ),
            Check(
                code="nicht_exportiert",
                label="Alle Buchungen sind nach Banana übergeben",
                detail=(
                    f"{len(nicht_exportiert)} Buchung(en) waren noch in keinem Export-Stapel."
                    if nicht_exportiert
                    else "Jede Buchung ist genau einmal exportiert."
                ),
                severity=SEVERITY_WARNUNG,
                count=len(nicht_exportiert),
                booking_ids=nicht_exportiert[:50],
            ),
            Check(
                code="doppelte",
                label="Keine doppelten Buchungen",
                detail="Gleiches Datum, gleicher Betrag, gleicher Text.",
                severity=SEVERITY_WARNUNG,
                count=len(doppelte),
                booking_ids=doppelte[:50],
            ),
            Check(
                code="mwst_stimmt",
                label="MWST-Betrag passt zum Satz",
                detail="Der gebuchte Steuerbetrag weicht vom Prozentsatz ab.",
                severity=SEVERITY_WARNUNG,
                count=len(mwst_streit),
                booking_ids=mwst_streit[:50],
            ),
        ]

    # ── Ausgabe ──────────────────────────────────────────────────────────────

    async def pdf(self, jahr: int | None = None) -> tuple[JahrReport, bytes]:
        report = await self.report(jahr)
        return report, render_pdf(report)

    async def paket(self, jahr: int | None = None) -> tuple[JahrReport, bytes]:
        """PDF + Banana-Datei + alle Belege des Jahres in einem ZIP."""
        report = await self.report(jahr)
        first, last = year_bounds(report.jahr)
        bookings = [b for b in await self._bookings() if (d := parse_date(b.datum or "")) and first <= d <= last]
        documents = [
            d for d in await self._documents() if d.invoice_date and first <= d.invoice_date <= last and d.file_key
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"jahresabschluss-{report.jahr}.pdf", render_pdf(report))
            archive.writestr(f"buchungen-{report.jahr}.txt", render_banana(bookings))
            archive.writestr(f"pruefliste-{report.jahr}.txt", render_checklist(report))
            for document in documents:
                content = read_receipt(document.file_key, self.tenant_id)
                if content:
                    name = document.filename or f"beleg-{document.id}"
                    archive.writestr(f"belege/{document.id}_{name}", content)
        logger.info("jahresabschluss %s: Paket mit %s Belegen", report.jahr, len(documents))
        return report, buffer.getvalue()


# ── Rendering ────────────────────────────────────────────────────────────────


def render_checklist(report: JahrReport) -> str:
    lines = [
        f"Prüfliste Jahresabschluss {report.jahr}",
        "=" * 40,
        "",
    ]
    for check in report.checks:
        mark = "OK " if not check.count else ("!! " if check.severity == SEVERITY_BLOCKER else " ! ")
        lines.append(f"{mark}{check.label}" + (f" ({check.count})" if check.count else ""))
        if check.detail:
            lines.append(f"    {check.detail}")
    lines += ["", f"Gewinn: CHF {fmt_swiss(report.gewinn)}", f"Buchungen: {report.buchungen}"]
    return "\n".join(lines) + "\n"


def render_pdf(report: JahrReport) -> bytes:
    """Bilanz, Erfolgsrechnung, Abschreibungsvorschlag und Prüfliste auf A4."""
    doc = PdfDoc(
        Meta(
            title=f"Jahresabschluss {report.jahr}",
            subtitle="Bilanz, Erfolgsrechnung und Abschreibungsvorschlag",
            company=report.company,
            period=f"1. Januar bis 31. Dezember {report.jahr}",
            footer=f"Jahresabschluss {report.jahr} · {report.company}".strip(" ·"),
            extra=[("Buchungen", str(report.buchungen))],
        )
    )

    doc.section("Bilanz per 31.12.", "Bestände aus allen Buchungen bis zum 31. Dezember.")
    columns = money_columns("Bezeichnung")
    rows = [Row([p.konto, p.bezeichnung, p.saldo]) for p in report.aktiven.positionen] or [
        Row(["", "Keine Aktivkonten bebucht", 0.0])
    ]
    rows.append(Row(["", "Total Aktiven", report.aktiven.total], bold=True, top_line=True))
    doc.table(columns, rows)

    doc.section("")
    rows = [Row([p.konto, p.bezeichnung, p.saldo]) for p in report.passiven.positionen] or [
        Row(["", "Keine Passivkonten bebucht", 0.0])
    ]
    rows.append(Row(["", "Total Passiven", report.passiven.total], bold=True, top_line=True))
    rows.append(Row(["", f"Gewinn {report.jahr}", report.gewinn], bold=True))
    rows.append(Row(["", "Total Passiven und Gewinn", report.passiven.total + report.gewinn], bold=True, top_line=True))
    doc.table(columns, rows)

    if abs(report.bilanz_differenz) > TOLERANCE:
        doc.paragraph(
            f"Differenz Aktiven zu Passiven und Gewinn: CHF {fmt_swiss(report.bilanz_differenz)}. "
            "Solange keine Eröffnungsbilanz erfasst ist, ist das erwartet — dieses System bucht ab dem "
            "ersten Beleg und kennt die Anfangsbestände nicht."
        )

    doc.page_break()
    doc.section("Erfolgsrechnung", f"Nur Buchungen mit Datum im Jahr {report.jahr}.")
    rows = []
    for gruppe in report.ertrag:
        rows.append(Row(["", gruppe.label, None], bold=True))
        rows += [Row([p.konto, p.bezeichnung, p.saldo]) for p in gruppe.positionen]
    rows.append(Row(["", "Total Ertrag", report.ertrag_total], bold=True, top_line=True))
    for gruppe in report.aufwand:
        rows.append(Row(["", gruppe.label, None], bold=True))
        rows += [Row([p.konto, p.bezeichnung, p.saldo]) for p in gruppe.positionen]
    rows.append(Row(["", "Total Aufwand", report.aufwand_total], bold=True, top_line=True))
    rows.append(Row(["", f"Gewinn {report.jahr}", report.gewinn], bold=True, top_line=True))
    doc.table(columns, rows)

    doc.section("Abschreibungsvorschlag", ESTV_QUELLE + ". Linear wäre die Hälfte des Satzes.")
    if report.abschreibungen:
        abschreibung_columns = [
            Column("Konto", 22.0, "L"),
            Column("Bezeichnung", 78.0, "L"),
            Column("Buchwert", 30.0, "R", money=True),
            Column("Satz", 14.0, "R"),
            Column("Abschreibung", 30.0, "R", money=True),
        ]
        doc.table(
            abschreibung_columns,
            [Row([a.konto, a.bezeichnung, a.buchwert, f"{a.satz:.0f}%", a.betrag]) for a in report.abschreibungen]
            + [
                Row(
                    ["", "Total", None, "", sum(a.betrag for a in report.abschreibungen)],
                    bold=True,
                    top_line=True,
                )
            ],
        )
        doc.paragraph(
            f"Buchungsvorschlag: {ABSCHREIBUNGSKONTO} Abschreibungen an das jeweilige Anlagekonto, "
            "per 31.12. Der Treuhänder entscheidet, ob degressiv oder linear gebucht wird."
        )
    else:
        doc.paragraph("Kein Anlagevermögen mit Buchwert — nichts abzuschreiben.")

    doc.section("Prüfliste")
    check_columns = [
        Column("Status", 20.0, "L"),
        Column("Prüfung", 90.0, "L"),
        Column("Hinweis", CONTENT_WIDTH - 110.0, "L"),
    ]
    doc.table(
        check_columns,
        [
            Row(
                [
                    "OK" if not c.count else ("Blocker" if c.severity == SEVERITY_BLOCKER else "Hinweis"),
                    c.label + (f" ({c.count})" if c.count else ""),
                    c.detail[:70],
                ]
            )
            for c in report.checks
        ],
    )
    return doc.output()
