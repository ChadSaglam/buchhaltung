"""LohnService — payroll against the database (B-72).

The engine in ``services/lohn.py`` is pure; this is the part that knows about
tenants, that reads the year-to-date gross out of the payslips already issued,
and that turns an issued payslip into bookings.

Issuing is the one irreversible step, so it is the one with rules:

* a payslip is issued once. The unique constraint on (tenant, employee, period)
  is the guard, not a SELECT-then-INSERT that two requests can interleave;
* an issued payslip never changes. A correction is a new payslip, and until one
  exists the old one is what was paid;
* issuing writes three bookings in the same transaction as the payslip. A
  payslip without its bookings would be a wage that the books do not know about,
  which is exactly the state the year-end reconciliation cannot resolve.

The three bookings are the standard KMU pattern:

    5000 / 2270   employee deductions   (owed to the Ausgleichskasse etc.)
    5000 / 1020   net pay               (leaves the bank)
    5700 / 2270   employer share        (our own cost)

5000 is therefore debited with the full gross, which is what the P&L needs to
show, and 2270 carries everything that is owed onward until it is paid.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models.booking import Booking
from app.models.lohn_settings import LohnSettings
from app.models.lohnabrechnung import STATUS_ABGERECHNET, Lohnabrechnung
from app.models.mitarbeiter import Mitarbeiter
from app.models.user import User
from app.services.lohn import LohnKonfigurationFehlt, Lohnlauf, abzug, ag_beitrag, berechnen

logger = logging.getLogger(__name__)

BOOKING_SOURCE = "lohn"
MAX_MITARBEITER = 500

#: Fields a client may set on an employee. Everything else (tenant, timestamps)
#: belongs to the server.
MITARBEITER_FELDER = frozenset(
    {
        "vorname",
        "name",
        "ahv_nummer",
        "geburtsdatum",
        "eintritt",
        "austritt",
        "pensum",
        "monatslohn",
        "dreizehnter",
        "kinder",
        "kanton",
        "quellensteuer",
        "quellensteuer_satz",
        "quellensteuer_tarif",
        "bvg_an_monat",
        "bvg_ag_monat",
        "iban",
        "email",
    }
)

SETTINGS_FELDER = frozenset(
    {
        "ahv_satz_an",
        "alv_satz_an",
        "alv_jahresgrenze",
        "uvg_bu_satz",
        "uvg_nbu_satz",
        "uvgz_satz_an",
        "uvgz_satz_ag",
        "ktg_satz_an",
        "ktg_satz_ag",
        "fak_satz",
        "verwaltungskosten_satz",
        "konto_lohnaufwand",
        "konto_sozialversicherung",
        "konto_verbindlichkeit",
        "konto_bank",
    }
)

#: Rates that mean "not insured" when absent, so clearing them is a real edit
#: and not the same thing as leaving a required field empty.
CLEARABLE = frozenset(
    {"uvgz_satz_an", "uvgz_satz_ag", "ktg_satz_an", "ktg_satz_ag", "quellensteuer_satz", "bvg_an_monat", "bvg_ag_monat"}
)


def _swiss_date(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def _monatsende(jahr: int, monat: int) -> date:
    from calendar import monthrange

    return date(jahr, monat, monthrange(jahr, monat)[1])


class LohnService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    # ── Einstellungen ────────────────────────────────────────────────────────

    async def settings(self) -> LohnSettings:
        """The tenant's rates, created empty on first use."""
        row = await self.db.execute(select(LohnSettings).where(LohnSettings.tenant_id == self.tenant_id))
        found = row.scalar_one_or_none()
        if found is None:
            found = LohnSettings(tenant_id=self.tenant_id)
            self.db.add(found)
            await self.db.flush()
        return found

    async def freigeben(self, freigegeben: bool) -> LohnSettings:
        """Record (or withdraw) the sign-off that clears the watermark."""
        current = await self.settings()
        current.freigegeben = freigegeben
        current.freigegeben_am = datetime.now(UTC) if freigegeben else None
        await self.db.flush()
        return current

    async def update_settings(self, data: dict) -> LohnSettings:
        current = await self.settings()
        for key, value in data.items():
            if key not in SETTINGS_FELDER:
                continue
            if value is None and key not in CLEARABLE:
                continue
            setattr(current, key, value)
        await self.db.flush()
        return current

    # ── Mitarbeiter ──────────────────────────────────────────────────────────

    async def mitarbeiter_liste(self, *, inklusive_ausgetreten: bool = True) -> list[Mitarbeiter]:
        query = select(Mitarbeiter).where(Mitarbeiter.tenant_id == self.tenant_id)
        if not inklusive_ausgetreten:
            query = query.where(Mitarbeiter.austritt.is_(None))
        rows = await self.db.execute(query.order_by(Mitarbeiter.name, Mitarbeiter.vorname))
        return list(rows.scalars().all())

    async def mitarbeiter(self, mitarbeiter_id: int) -> Mitarbeiter:
        row = await self.db.execute(
            select(Mitarbeiter).where(Mitarbeiter.id == mitarbeiter_id, Mitarbeiter.tenant_id == self.tenant_id)
        )
        found = row.scalar_one_or_none()
        if found is None:
            raise HTTPException(404, "Mitarbeiter nicht gefunden.")
        return found

    async def mitarbeiter_anlegen(self, data: dict) -> Mitarbeiter:
        anzahl = len(await self.mitarbeiter_liste())
        if anzahl >= MAX_MITARBEITER:
            raise HTTPException(400, f"Maximal {MAX_MITARBEITER} Mitarbeitende.")
        werte = {k: v for k, v in data.items() if k in MITARBEITER_FELDER and v is not None}
        person = Mitarbeiter(tenant_id=self.tenant_id, **werte)
        self.db.add(person)
        await self.db.flush()
        return person

    async def mitarbeiter_aendern(self, mitarbeiter_id: int, data: dict) -> Mitarbeiter:
        person = await self.mitarbeiter(mitarbeiter_id)
        for key, value in data.items():
            if key not in MITARBEITER_FELDER:
                continue
            # austritt is clearable too: an employee can un-resign.
            if value is None and key not in CLEARABLE and key != "austritt":
                continue
            setattr(person, key, value)
        await self.db.flush()
        return person

    # ── Abrechnen ────────────────────────────────────────────────────────────

    async def brutto_ytd(self, mitarbeiter_id: int, jahr: int, *, vor_monat: int) -> float:
        """Gross already issued this year before ``vor_monat`` — the ALV cap base.

        Drafts do not count: an unissued payslip is a proposal, and counting it
        would make the cap depend on whether somebody left a preview lying around.
        """
        rows = await self.db.execute(
            select(Lohnabrechnung.brutto).where(
                Lohnabrechnung.tenant_id == self.tenant_id,
                Lohnabrechnung.mitarbeiter_id == mitarbeiter_id,
                Lohnabrechnung.jahr == jahr,
                Lohnabrechnung.monat < vor_monat,
                Lohnabrechnung.status == STATUS_ABGERECHNET,
            )
        )
        return float(sum(rows.scalars().all() or [0.0]))

    async def vorschau(
        self, mitarbeiter_id: int, jahr: int, monat: int, *, zulagen: float = 0.0, dreizehnter: bool = False
    ) -> tuple[Mitarbeiter, Lohnlauf]:
        """What this month would pay — no row written, nothing booked."""
        person = await self.mitarbeiter(mitarbeiter_id)
        settings = await self.settings()
        ytd = await self.brutto_ytd(mitarbeiter_id, jahr, vor_monat=monat)
        try:
            lauf = berechnen(
                mitarbeiter=person,
                settings=settings,
                jahr=jahr,
                monat=monat,
                zulagen=zulagen,
                dreizehnter=dreizehnter,
                brutto_ytd=ytd,
            )
        except LohnKonfigurationFehlt as exc:
            # A dedicated code, not a bare 400: the frontend has to send the user
            # to the rate settings, and "Request failed" gives it nothing to act on.
            raise ApiError(400, "lohn_konfiguration_fehlt", str(exc)) from exc
        return person, lauf

    async def abrechnen(
        self, mitarbeiter_id: int, jahr: int, monat: int, *, zulagen: float = 0.0, dreizehnter: bool = False
    ) -> tuple[Lohnabrechnung, list[Booking], Mitarbeiter, Lohnlauf]:
        """Issue the payslip and book it. Idempotent by the unique constraint."""
        person, lauf = await self.vorschau(mitarbeiter_id, jahr, monat, zulagen=zulagen, dreizehnter=dreizehnter)
        settings = await self.settings()

        row = Lohnabrechnung(
            tenant_id=self.tenant_id,
            mitarbeiter_id=person.id,
            jahr=jahr,
            monat=monat,
            status=STATUS_ABGERECHNET,
            abgerechnet_am=datetime.now(UTC),
            grundlohn=lauf.grundlohn,
            dreizehnter=lauf.dreizehnter,
            zulagen=lauf.zulagen,
            brutto=lauf.brutto,
            abzuege=lauf.abzuege_total,
            netto=lauf.netto,
            ag_total=lauf.ag_total,
        )
        for label, satz_feld, betrag_feld in (
            ("AHV/IV/EO", "ahv_satz", "ahv_betrag"),
            ("ALV", "alv_satz", "alv_betrag"),
            ("NBU", "nbu_satz", "nbu_betrag"),
            ("UVGZ", "uvgz_satz", "uvgz_betrag"),
            ("KTG", "ktg_satz", "ktg_betrag"),
            ("Quellensteuer", "quellensteuer_satz", "quellensteuer_betrag"),
        ):
            line = abzug(lauf, label)
            setattr(row, satz_feld, line.satz if line else 0.0)
            setattr(row, betrag_feld, line.betrag if line else 0.0)
        bvg = abzug(lauf, "BVG")
        row.bvg_betrag = bvg.betrag if bvg else 0.0
        alv = abzug(lauf, "ALV")
        row.alv_basis = alv.basis if alv else 0.0

        for label, feld in (
            ("AHV/IV/EO", "ag_ahv"),
            ("ALV", "ag_alv"),
            ("UVG BU", "ag_bu"),
            ("UVGZ", "ag_uvgz"),
            ("KTG", "ag_ktg"),
            ("FAK", "ag_fak"),
            ("Verwaltungskosten", "ag_verwaltungskosten"),
            ("BVG", "ag_bvg"),
        ):
            line = ag_beitrag(lauf, label)
            setattr(row, feld, line.betrag if line else 0.0)

        self.db.add(row)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(409, f"Lohnabrechnung {jahr}-{monat:02d} ist bereits abgerechnet.") from exc

        bookings = self._bookings(person, row, settings)
        self.db.add_all(bookings)
        await self.db.flush()
        logger.info(
            "Lohn %s-%02d für Mitarbeiter %s: brutto %s, netto %s",
            jahr,
            monat,
            person.id,
            row.brutto,
            row.netto,
        )
        return row, bookings, person, lauf

    def _bookings(self, person: Mitarbeiter, row: Lohnabrechnung, settings: LohnSettings) -> list[Booking]:
        tag = _swiss_date(_monatsende(row.jahr, row.monat))
        name = person.anzeige_name or f"Mitarbeiter {person.id}"
        quelle = f"lohn:{row.jahr}-{row.monat:02d}:{person.id}"

        def booking(beschreibung: str, betrag: float, soll: str, haben: str) -> Booking:
            return Booking(
                tenant_id=self.tenant_id,
                datum=tag,
                beschreibung=beschreibung,
                betrag=betrag,
                kt_soll=soll,
                kt_haben=haben,
                source=BOOKING_SOURCE,
                source_key=quelle,
            )

        rows = []
        if row.abzuege:
            rows.append(
                booking(
                    f"Lohnabzüge {name} {row.periode}",
                    row.abzuege,
                    settings.konto_lohnaufwand,
                    settings.konto_verbindlichkeit,
                )
            )
        if row.netto:
            rows.append(
                booking(
                    f"Nettolohn {name} {row.periode}",
                    row.netto,
                    settings.konto_lohnaufwand,
                    settings.konto_bank,
                )
            )
        if row.ag_total:
            rows.append(
                booking(
                    f"Arbeitgeberbeiträge {name} {row.periode}",
                    row.ag_total,
                    settings.konto_sozialversicherung,
                    settings.konto_verbindlichkeit,
                )
            )
        return rows

    # ── Lesen ────────────────────────────────────────────────────────────────

    async def abrechnung(self, abrechnung_id: int) -> tuple[Lohnabrechnung, Mitarbeiter]:
        row = await self.db.execute(
            select(Lohnabrechnung).where(Lohnabrechnung.id == abrechnung_id, Lohnabrechnung.tenant_id == self.tenant_id)
        )
        found = row.scalar_one_or_none()
        if found is None:
            raise HTTPException(404, "Lohnabrechnung nicht gefunden.")
        return found, await self.mitarbeiter(found.mitarbeiter_id)

    async def abrechnungen(self, *, jahr: int | None = None, mitarbeiter_id: int | None = None) -> list[Lohnabrechnung]:
        query = select(Lohnabrechnung).where(Lohnabrechnung.tenant_id == self.tenant_id)
        if jahr is not None:
            query = query.where(Lohnabrechnung.jahr == jahr)
        if mitarbeiter_id is not None:
            query = query.where(Lohnabrechnung.mitarbeiter_id == mitarbeiter_id)
        rows = await self.db.execute(
            query.order_by(Lohnabrechnung.jahr.desc(), Lohnabrechnung.monat.desc(), Lohnabrechnung.id.desc())
        )
        return list(rows.scalars().all())

    async def jahreslohn(self, mitarbeiter_id: int, jahr: int) -> list[Lohnabrechnung]:
        """Every issued payslip of a year, oldest first — the Lohnausweis basis."""
        rows = await self.db.execute(
            select(Lohnabrechnung)
            .where(
                Lohnabrechnung.tenant_id == self.tenant_id,
                Lohnabrechnung.mitarbeiter_id == mitarbeiter_id,
                Lohnabrechnung.jahr == jahr,
                Lohnabrechnung.status == STATUS_ABGERECHNET,
            )
            .order_by(Lohnabrechnung.monat)
        )
        return list(rows.scalars().all())
