"""MWST-Abrechnung (B-67) — Formular 200 aus den Buchungen.

Die Ziffern und ihre Reihenfolge folgen dem offiziellen Abrechnungsformular der
ESTV (effektive Methode, gültig ab 01.01.2024). Gerechnet wird nur, was in den
Buchungen steht; Ziffern, die kein Buchungssatz hergibt (Bezugsteuer,
Einlageentsteuerung, Korrekturen), stehen mit 0.00 da, damit der Nutzer sieht,
dass er sie selber prüfen muss — geraten wird nichts.

Seitenzuordnung der MwSt-Codes wie in Banana:
  V… = Umsatzsteuer  → Ziffer 302 / 312 / 342 (nach Satz)
  M… = Vorsteuer auf Material und Dienstleistungen → Ziffer 400
  I… = Vorsteuer auf Investitionen und übrigem Betriebsaufwand → Ziffer 405
Fehlt der Code, entscheiden die Konten (3… im Haben = Umsatz, 4… im Soll =
Material/DL, 5…/6… und Anlagen 15…/16…/17… = Investitionen/Betriebsaufwand) — und die Zeile wird als
Hinweis gemeldet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.user import User
from app.services.classifier import VAT_CODE_BY_RATE, calc_mwst
from app.services.documents import parse_date
from app.services.export import fmt_swiss, round_chf
from app.services.export_batch import SEVERITY_BLOCKER, SEVERITY_WARNUNG, Check, vat_disagrees

logger = logging.getLogger(__name__)

METHODE_EFFEKTIV = "effektiv"
METHODE_SALDO = "saldo"
METHODEN = (METHODE_EFFEKTIV, METHODE_SALDO)

# Normal-, reduzierter und Beherbergungssatz → Ziffer der Steuerberechnung.
RATE_TO_ZIFFER = {8.1: "302", 2.6: "312", 3.8: "342", 7.7: "302", 2.5: "312", 3.7: "342"}
ZIFFER_LABEL = {
    "200": "Total der vereinbarten bzw. vereinnahmten Entgelte",
    "205": "Entgelte aus optierten Leistungen (Art. 22)",
    "220": "Von der Steuer befreite Leistungen (u. a. Exporte, Art. 23)",
    "221": "Leistungen mit Leistungsort im Ausland",
    "225": "Übertragung im Meldeverfahren (Art. 38)",
    "230": "Von der Steuer ausgenommene Inlandleistungen (Art. 21)",
    "235": "Entgeltsminderungen (Skonti, Rabatte, Verluste)",
    "280": "Diverses",
    "289": "Total Abzüge (Ziffern 220–280)",
    "299": "Steuerbarer Gesamtumsatz (200 ./. 289)",
    "302": "Leistungen zum Normalsatz",
    "312": "Leistungen zum reduzierten Satz",
    "342": "Leistungen zum Beherbergungssatz",
    "382": "Bezugsteuer",
    "399": "Total geschuldete Steuer",
    "400": "Vorsteuer auf Material- und Dienstleistungsaufwand",
    "405": "Vorsteuer auf Investitionen und übrigem Betriebsaufwand",
    "410": "Einlageentsteuerung (Art. 32)",
    "415": "Vorsteuerkorrekturen (Art. 30, 31)",
    "420": "Vorsteuerkürzungen (Art. 33 Abs. 2)",
    "479": "Total Vorsteuerabzüge",
    "500": "Zu bezahlender Betrag",
    "510": "Guthaben der steuerpflichtigen Person",
}

SIDE_UMSATZ = "umsatz"
SIDE_MATERIAL = "material"
SIDE_INVEST = "invest"
SIDE_KEINE = "keine"


def quarter_bounds(quartal: str) -> tuple[date, date]:
    """'2026-Q2' → (1.4.2026, 30.6.2026)."""
    try:
        year_text, quarter_text = quartal.upper().split("-Q")
        year, quarter = int(year_text), int(quarter_text)
        if quarter not in (1, 2, 3, 4):
            raise ValueError(quarter)
        first_month = 3 * (quarter - 1) + 1
        last_month = first_month + 2
        last_day = 31 if last_month in (3, 12) else 30
        return date(year, first_month, 1), date(year, last_month, last_day)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(400, "Quartal im Format JJJJ-Qn angeben, z. B. 2026-Q2.") from exc


def quarter_key(day: date | None) -> str | None:
    return f"{day.year:04d}-Q{(day.month - 1) // 3 + 1}" if day else None


def quarter_label(quartal: str) -> str:
    first, last = quarter_bounds(quartal)
    return f"{first.strftime('%d.%m.%Y')} – {last.strftime('%d.%m.%Y')}"


def default_quarter(days: list[date], today: date | None = None) -> str:
    now = today or datetime.now(UTC).date()
    newest = max(days) if days else now
    return f"{newest.year:04d}-Q{(newest.month - 1) // 3 + 1}"


def booking_rate(booking: Booking) -> float | None:
    """The VAT rate of a booking, from its percentage — None when it carries no VAT."""
    raw = (booking.mwst_pct or "").strip()
    if not raw:
        return None
    try:
        rate = abs(float(raw))
    except ValueError:
        return None
    return rate or None


def code_side(code: str) -> str:
    """Which side of the form a Banana VAT code belongs to."""
    prefix = (code or "").strip()[:1].upper()
    if prefix == "V":
        return SIDE_UMSATZ
    if prefix == "M":
        return SIDE_MATERIAL
    if prefix == "I":
        return SIDE_INVEST
    return SIDE_KEINE


def account_side(booking: Booking) -> str:
    """Fallback when no code says it: the accounts do."""
    haben = (booking.kt_haben or "").strip()
    soll = (booking.kt_soll or "").strip()
    if haben.startswith("3"):
        return SIDE_UMSATZ
    if soll.startswith("4"):
        return SIDE_MATERIAL
    # 5…/6… = Personal- und Betriebsaufwand, 15…/16…/17… = Anlagen (Investitionen).
    # 10…/11… (Bank, Debitoren) sind kein Aufwand und bleiben ohne Seite.
    if soll[:1] in {"5", "6"} or soll[:2] in {"15", "16", "17"}:
        return SIDE_INVEST
    return SIDE_KEINE


def booking_side(booking: Booking) -> str:
    """The code decides; without one the accounts do."""
    from_code = code_side(booking.mwst_code or "")
    return from_code if from_code != SIDE_KEINE else account_side(booking)


def side_disagrees_with_accounts(booking: Booking) -> bool:
    """A V-code on an expense (or M/I on revenue) puts the money in the wrong Ziffer."""
    from_code = code_side(booking.mwst_code or "")
    if from_code == SIDE_KEINE:
        return False
    from_accounts = account_side(booking)
    if from_accounts == SIDE_KEINE:
        return False
    if from_code == SIDE_UMSATZ:
        return from_accounts != SIDE_UMSATZ
    return from_accounts == SIDE_UMSATZ


def tax_of(booking: Booking) -> float:
    """The VAT in the booking: the stored amount, else computed from gross and rate."""
    stored = float(booking.mwst_amount or 0.0)
    if stored:
        return float(round_chf(abs(stored)))
    computed = calc_mwst(float(booking.betrag or 0.0), booking.mwst_pct or "")
    return float(round_chf(abs(float(computed)))) if computed != "" else 0.0


def is_revenue_reduction(booking: Booking) -> bool:
    """A credit note: revenue account on the debit side, or a negative revenue amount."""
    if (booking.kt_soll or "").strip().startswith("3"):
        return True
    return booking_side(booking) == SIDE_UMSATZ and float(booking.betrag or 0.0) < 0


@dataclass
class ZifferRow:
    ziffer: str
    label: str
    umsatz: float | None  # only the Steuerberechnung rows carry both
    steuer: float | None
    rate: float | None = None


@dataclass
class MwstReport:
    quartal: str
    zeitraum: str
    methode: str
    satz: float | None  # Saldosteuersatz, only for methode="saldo"
    buchungen: int
    ziffern: list[ZifferRow] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)

    @property
    def blockers(self) -> int:
        return sum(1 for c in self.checks if c.severity == SEVERITY_BLOCKER and c.count)

    @property
    def ready(self) -> bool:
        return self.blockers == 0

    def value(self, ziffer: str) -> float:
        row = next((r for r in self.ziffern if r.ziffer == ziffer), None)
        if row is None:
            return 0.0
        return float(row.steuer if row.steuer is not None else (row.umsatz or 0.0))


def copy_block(report: MwstReport) -> str:
    """Tab-separated Ziffer + Betrag, ready to paste into the ePortal form."""
    lines = [f"# MWST-Abrechnung {report.quartal} ({report.zeitraum}) — {report.methode}"]
    if report.satz:
        lines.append(f"# Saldosteuersatz {report.satz:.1f} %")
    for row in report.ziffern:
        amount = row.steuer if row.steuer is not None else row.umsatz
        lines.append(f"{row.ziffer}\t{amount if amount is not None else 0.0:.2f}\t{row.label}")
    lines.append("# Entwurf aus den Buchungen — vor dem Einreichen prüfen.")
    return "\n".join(lines) + "\n"


def render_text(report: MwstReport) -> str:
    """The human-readable sheet (print or send to the Treuhänder)."""
    lines = [
        f"MWST-Abrechnung {report.quartal}",
        "=" * 44,
        f"Zeitraum:  {report.zeitraum}",
        f"Methode:   {'Saldosteuersatz' if report.methode == METHODE_SALDO else 'effektiv'}"
        + (f" ({report.satz:.1f} %)" if report.satz else ""),
        f"Buchungen: {report.buchungen}",
        "",
    ]
    for row in report.ziffern:
        amount = row.steuer if row.steuer is not None else row.umsatz
        umsatz_note = ""
        if row.steuer is not None and row.umsatz is not None:
            umsatz_note = f"  (Umsatz CHF {fmt_swiss(row.umsatz)})"
        lines.append(f"{row.ziffer}  {row.label:<52} CHF {fmt_swiss(amount or 0.0):>14}{umsatz_note}")
    lines += [
        "",
        "Entwurf aus den Buchungen. Ziffern ohne Buchungsgrundlage (Bezugsteuer,",
        "Einlageentsteuerung, Korrekturen, Kürzungen) stehen auf 0.00 und sind selber",
        "zu prüfen.",
    ]
    return "\n".join(lines) + "\n"


class MwstService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    async def _bookings(self) -> list[Booking]:
        rows = await self.db.execute(select(Booking).where(Booking.tenant_id == self.tenant_id).order_by(Booking.id))
        return list(rows.scalars().all())

    async def quarters(self) -> list[str]:
        keys = {quarter_key(parse_date(b.datum or "")) for b in await self._bookings()}
        return sorted((k for k in keys if k), reverse=True)

    async def report(
        self,
        quartal: str | None = None,
        methode: str = METHODE_EFFEKTIV,
        satz: float | None = None,
        today: date | None = None,
    ) -> MwstReport:
        if methode not in METHODEN:
            raise HTTPException(400, "Methode ist 'effektiv' oder 'saldo'.")
        if methode == METHODE_SALDO and not satz:
            raise HTTPException(400, "Für die Saldosteuersatz-Methode den Satz angeben, z. B. 6.5.")
        if satz is not None and not 0 < satz <= 15:
            raise HTTPException(400, "Saldosteuersatz muss zwischen 0 und 15 % liegen.")

        all_bookings = await self._bookings()
        if quartal is None:
            days = [d for d in (parse_date(b.datum or "") for b in all_bookings) if d is not None]
            quartal = default_quarter(days, today)
        first, _last = quarter_bounds(quartal)
        key = f"{first.year:04d}-Q{(first.month - 1) // 3 + 1}"
        bookings = [b for b in all_bookings if quarter_key(parse_date(b.datum or "")) == key]

        umsatz_rows = [b for b in bookings if booking_side(b) == SIDE_UMSATZ and not is_revenue_reduction(b)]
        reductions = [b for b in bookings if is_revenue_reduction(b)]
        material_rows = [b for b in bookings if booking_side(b) == SIDE_MATERIAL]
        invest_rows = [b for b in bookings if booking_side(b) == SIDE_INVEST]

        ziffer_200 = float(round_chf(sum(abs(float(b.betrag or 0.0)) for b in umsatz_rows)))
        ziffer_235 = float(round_chf(sum(abs(float(b.betrag or 0.0)) for b in reductions)))
        ziffer_289 = ziffer_235  # 220/221/225/230/280 sind nicht aus Buchungen ableitbar
        ziffer_299 = float(round_chf(Decimal(str(ziffer_200)) - Decimal(str(ziffer_289))))

        rows: list[ZifferRow] = [
            ZifferRow("200", ZIFFER_LABEL["200"], ziffer_200, None),
            ZifferRow("205", ZIFFER_LABEL["205"], 0.0, None),
            ZifferRow("220", ZIFFER_LABEL["220"], 0.0, None),
            ZifferRow("221", ZIFFER_LABEL["221"], 0.0, None),
            ZifferRow("225", ZIFFER_LABEL["225"], 0.0, None),
            ZifferRow("230", ZIFFER_LABEL["230"], 0.0, None),
            ZifferRow("235", ZIFFER_LABEL["235"], ziffer_235, None),
            ZifferRow("280", ZIFFER_LABEL["280"], 0.0, None),
            ZifferRow("289", ZIFFER_LABEL["289"], ziffer_289, None),
            ZifferRow("299", ZIFFER_LABEL["299"], ziffer_299, None),
        ]

        if methode == METHODE_SALDO:
            steuer = float(round_chf(Decimal(str(ziffer_299)) * Decimal(str(satz)) / Decimal("100")))
            rows.append(
                ZifferRow(
                    "322",
                    f"Umsatz zum Saldosteuersatz {satz:.1f} % (Ziffer nach Satz, 322 ff.)",
                    ziffer_299,
                    steuer,
                    rate=satz,
                )
            )
            rows.append(ZifferRow("399", ZIFFER_LABEL["399"], None, steuer))
            rows.append(ZifferRow("500", ZIFFER_LABEL["500"], None, steuer))
            rows.append(ZifferRow("510", ZIFFER_LABEL["510"], None, 0.0))
        else:
            by_ziffer: dict[str, tuple[float, float, float]] = {}
            for booking in umsatz_rows:
                rate = booking_rate(booking)
                ziffer = RATE_TO_ZIFFER.get(round(rate, 1)) if rate else None
                if ziffer is None:
                    continue
                gross, tax, _ = by_ziffer.get(ziffer, (0.0, 0.0, 0.0))
                by_ziffer[ziffer] = (
                    gross + abs(float(booking.betrag or 0.0)),
                    tax + tax_of(booking),
                    rate or 0.0,
                )
            for ziffer in ("302", "312", "342"):
                gross, tax, rate = by_ziffer.get(ziffer, (0.0, 0.0, 0.0))
                rows.append(
                    ZifferRow(
                        ziffer,
                        ZIFFER_LABEL[ziffer],
                        float(round_chf(gross)),
                        float(round_chf(tax)),
                        rate=rate or None,
                    )
                )
            rows.append(ZifferRow("382", ZIFFER_LABEL["382"], 0.0, 0.0))
            geschuldet = float(round_chf(sum(r.steuer or 0.0 for r in rows if r.ziffer in ("302", "312", "342"))))
            rows.append(ZifferRow("399", ZIFFER_LABEL["399"], None, geschuldet))

            vorsteuer_400 = float(round_chf(sum(tax_of(b) for b in material_rows)))
            vorsteuer_405 = float(round_chf(sum(tax_of(b) for b in invest_rows)))
            rows.append(ZifferRow("400", ZIFFER_LABEL["400"], None, vorsteuer_400))
            rows.append(ZifferRow("405", ZIFFER_LABEL["405"], None, vorsteuer_405))
            rows.append(ZifferRow("410", ZIFFER_LABEL["410"], None, 0.0))
            rows.append(ZifferRow("415", ZIFFER_LABEL["415"], None, 0.0))
            rows.append(ZifferRow("420", ZIFFER_LABEL["420"], None, 0.0))
            vorsteuer = float(round_chf(Decimal(str(vorsteuer_400)) + Decimal(str(vorsteuer_405))))
            rows.append(ZifferRow("479", ZIFFER_LABEL["479"], None, vorsteuer))
            saldo = float(round_chf(Decimal(str(geschuldet)) - Decimal(str(vorsteuer))))
            rows.append(ZifferRow("500", ZIFFER_LABEL["500"], None, max(saldo, 0.0)))
            rows.append(ZifferRow("510", ZIFFER_LABEL["510"], None, max(-saldo, 0.0)))

        checks = self._checks(bookings, umsatz_rows, material_rows, invest_rows)
        logger.info("mwst %s (%s): %s bookings", key, methode, len(bookings))
        return MwstReport(
            quartal=key,
            zeitraum=quarter_label(key),
            methode=methode,
            satz=satz if methode == METHODE_SALDO else None,
            buchungen=len(bookings),
            ziffern=rows,
            checks=checks,
        )

    def _checks(
        self,
        bookings: list[Booking],
        umsatz_rows: list[Booking],
        material_rows: list[Booking],
        invest_rows: list[Booking],
    ) -> list[Check]:
        vat_broken = [b.id for b in bookings if vat_disagrees(b)]
        wrong_side = [b.id for b in bookings if side_disagrees_with_accounts(b)]
        unknown_rate = [
            b.id
            for b in umsatz_rows
            if (rate := booking_rate(b)) is not None and round(rate, 1) not in VAT_CODE_BY_RATE
        ]
        expense_without_vat = [b.id for b in (material_rows + invest_rows) if not (b.mwst_pct or "").strip()]
        revenue_without_vat = [b.id for b in umsatz_rows if not (b.mwst_pct or "").strip()]
        no_side = [b.id for b in bookings if booking_side(b) == SIDE_KEINE]

        return [
            Check(
                code="mwst_unstimmig",
                label="MwSt-Satz und MwSt-Code passen zusammen",
                detail="Ein falscher Code verschiebt Geld in die falsche Ziffer.",
                severity=SEVERITY_BLOCKER,
                count=len(vat_broken),
                booking_ids=vat_broken[:20],
            ),
            Check(
                code="code_seite_falsch",
                label="Umsatz- und Vorsteuercodes stehen auf der richtigen Seite",
                detail="V… gehört zum Umsatz, M…/I… zur Vorsteuer — hier widersprechen sich Code und Konten.",
                severity=SEVERITY_BLOCKER,
                count=len(wrong_side),
                booking_ids=wrong_side[:20],
            ),
            Check(
                code="satz_unbekannt",
                label="Alle Umsatzsätze sind gültige Schweizer Sätze",
                detail="Nur 8.1 / 2.6 / 3.8 % (bzw. 7.7 / 2.5 / 3.7 % vor 2024) haben eine Ziffer.",
                severity=SEVERITY_BLOCKER,
                count=len(unknown_rate),
                booking_ids=unknown_rate[:20],
            ),
            Check(
                code="vorsteuer_fehlt",
                label="Aufwandbuchungen haben eine Vorsteuer",
                detail="Ohne MwSt-Satz fällt die Vorsteuer aus Ziffer 400/405 — auf einem 4000er meist ein Fehler.",
                severity=SEVERITY_WARNUNG,
                count=len(expense_without_vat),
                booking_ids=expense_without_vat[:20],
            ),
            Check(
                code="umsatz_ohne_mwst",
                label="Umsatzbuchungen haben einen Satz",
                detail="Steuerbefreite oder ausgenommene Umsätze gehören in Ziffer 220–230.",
                severity=SEVERITY_WARNUNG,
                count=len(revenue_without_vat),
                booking_ids=revenue_without_vat[:20],
            ),
            Check(
                code="ohne_seite",
                label="Jede Buchung ist einer Seite zuordenbar",
                detail="Weder Code noch Konten sagen, ob Umsatz oder Vorsteuer — diese Zeilen fehlen im Formular.",
                severity=SEVERITY_WARNUNG,
                count=len(no_side),
                booking_ids=no_side[:20],
            ),
        ]
