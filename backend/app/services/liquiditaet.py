"""Liquidität und Steuerrückstellung (B-71).

Zwei Fragen, die ein Inhaber sich jeden Monat stellt und die Buchhaltung heute
nicht beantwortet:

* *Reicht das Geld die nächsten 90 Tage?* — Kontostand plus was hereinkommt,
  minus was hinausgeht: offene Debitoren, offene Kreditoren und die Beträge,
  die jeden Monat gleich abgehen (Miete, Leasing, Versicherung). Letztere
  werden **aus den eigenen Buchungen erkannt**, nicht getippt.
* *Wie viel Steuern muss ich zurücklegen?* — Gewinn seit Jahresbeginn mal dem
  Satz, den der Treuhänder genannt hat, minus dem, was schon zurückgelegt ist.

Die Ehrlichkeiten (wie in ``jahresabschluss.py``):

* **Der Kontostand ist nur das, was dieses System gebucht hat.** Ohne
  Eröffnungsbilanz fehlt der Anfangsbestand — das steht als Warnung dran, statt
  eine Zahl zu zeigen, der niemand trauen kann.
* **Der Steuersatz wird nicht erraten.** Die effektive Gewinnsteuer hängt von
  Kanton *und* Gemeinde ab; ohne hinterlegten Satz gibt es keine Schätzung,
  sondern die Bandbreite und die Quelle, damit der Inhaber seinen Satz holt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.company_profile import CompanyProfile
from app.models.document import (
    DIRECTION_AUSGANG,
    STATUS_OFFEN,
    Document,
)
from app.models.user import User
from app.services.dauerbuchungen import Dauerbuchung, erkennen, monatsschluessel
from app.services.documents import parse_date
from app.services.export import round_chf as _round_chf
from app.services.offene_posten import DEFAULT_TERMS_DAYS, effective_due_date, today_utc

logger = logging.getLogger(__name__)


def chf(value) -> float:
    """Round to the franc-and-rappen the same way the columns do, as a float.

    ``round_chf`` returns a ``Decimal``; every number in this module is arithmetic
    on plain floats and ends up in JSON, so it is converted once, here.
    """
    return float(_round_chf(value))


HORIZONT_TAGE = 90

# KMU-Kontenrahmen, Gruppe 10 "Flüssige Mittel": 100 Kasse, 102 Bank, …
# 106 sind Wertschriften mit Börsenkurs — Geld, aber nicht auf dem Konto.
LIQUIDE_PRAEFIXE = ("100", "101", "102", "103", "104", "105")
# Gruppe 3 Betriebsertrag, Gruppen 4–8 Aufwand: die Erfolgsrechnung.
ERTRAG_PRAEFIX = "3"
AUFWAND_PRAEFIXE = ("4", "5", "6", "7", "8")
# Wohin eine Steuerrückstellung gebucht wird (KMU-Kontenrahmen).
KONTO_STEUERRUECKSTELLUNG = "2201"
KONTO_STEUERAUFWAND = "8900"

# Effektive Gewinnsteuer (Bund + Kanton + Gemeinde) am Kantonshauptort, 2026.
# Bandbreite und Mittel, keine Kantonstabelle: die Gemeinde entscheidet mit, und
# ein falscher Satz hier wäre eine Zahl, die jemand glaubt.
GEWINNSTEUER_MIN = 11.66  # Luzern
GEWINNSTEUER_MITTEL = 14.43
GEWINNSTEUER_MAX = 20.54  # Bern
GEWINNSTEUER_QUELLE = (
    "Effektive Gewinnsteuer 2026 (Bund, Kanton, Gemeinde) am Kantonshauptort: "
    f"{GEWINNSTEUER_MIN:.2f} % (LU) bis {GEWINNSTEUER_MAX:.2f} % (BE), Mittel {GEWINNSTEUER_MITTEL:.2f} %. "
    "Der Bund erhebt 8.5 % vom Gewinn nach Steuern (7.83 % vom Gewinn vor Steuern). "
    "Quelle: ESTV, Kantonaler Vergleich der Steuerbelastung 2026."
)


def _liquide(konto: str) -> bool:
    return (konto or "").startswith(LIQUIDE_PRAEFIXE)


@dataclass
class Position:
    """Ein erwarteter Geldfluss. ``betrag`` ist positiv für Eingang."""

    datum: date
    label: str
    betrag: float
    quelle: str  # debitor | kreditor | dauerbuchung
    document_id: int | None = None
    ueberfaellig: bool = False


@dataclass
class Monat:
    schluessel: str
    label: str
    eingang: float
    ausgang: float
    saldo_ende: float


@dataclass
class Steuer:
    """Was für die Gewinnsteuer zurückzulegen wäre."""

    jahr: int
    ertrag: float
    aufwand: float
    gewinn: float
    satz: float | None
    rueckstellung_soll: float | None
    schon_zurueckgestellt: float
    offen: float | None
    pro_quartal: float | None
    quelle: str = GEWINNSTEUER_QUELLE
    hinweis: str = ""


@dataclass
class LiquiditaetReport:
    stichtag: date
    bis: date
    stand_heute: float
    eingang: float
    ausgang: float
    prognose: float
    tiefster_stand: float
    tiefster_am: date
    positionen: list[Position] = field(default_factory=list)
    dauerbuchungen: list[Dauerbuchung] = field(default_factory=list)
    monate: list[Monat] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)
    steuer: Steuer | None = None


MONATSNAMEN = (
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


def monatslabel(d: date) -> str:
    return f"{MONATSNAMEN[d.month - 1]} {d.year}"


class LiquiditaetService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    # --- Buchungen ---------------------------------------------------------

    async def _bookings(self) -> list[Booking]:
        result = await self.db.execute(select(Booking).where(Booking.tenant_id == self.tenant_id))
        return list(result.scalars().all())

    async def _profile(self) -> CompanyProfile | None:
        result = await self.db.execute(select(CompanyProfile).where(CompanyProfile.tenant_id == self.tenant_id))
        return result.scalar_one_or_none()

    async def _open_documents(self) -> list[Document]:
        result = await self.db.execute(
            select(Document).where(Document.tenant_id == self.tenant_id, Document.status == STATUS_OFFEN)
        )
        return [d for d in result.scalars().all() if d.amount]

    # --- Kontostand --------------------------------------------------------

    @staticmethod
    def kontostand(bookings: list[Booking]) -> float:
        """Was auf Kasse und Bank liegt — Soll erhöht, Haben verringert."""
        saldo = 0.0
        for b in bookings:
            betrag = float(b.betrag or 0)
            if _liquide(b.kt_soll):
                saldo += betrag
            if _liquide(b.kt_haben):
                saldo -= betrag
        return chf(saldo)

    # --- Dauerbuchungen (B-74 owns the detection) ---------------------------

    @staticmethod
    def dauerbuchungen(bookings: list[Booking], heute: date) -> list[Dauerbuchung]:
        """The recurring outgoings — recognised by `services/dauerbuchungen.py` (B-74)."""
        return erkennen(bookings, heute)

    @staticmethod
    def dauer_positionen(dauer: list[Dauerbuchung], heute: date, bis: date) -> list[Position]:
        """Jede Dauerbuchung einmal pro Monat im Fenster, am selben Tag wie heute."""
        positionen: list[Position] = []
        for eintrag in dauer:
            for monat in range(1, 4):
                jahr = heute.year + (heute.month - 1 + monat) // 12
                m = (heute.month - 1 + monat) % 12 + 1
                tag = min(heute.day, 28)
                faellig = date(jahr, m, tag)
                if faellig > bis:
                    break
                positionen.append(
                    Position(
                        datum=faellig,
                        label=eintrag.label,
                        betrag=-eintrag.betrag,
                        quelle="dauerbuchung",
                    )
                )
        return positionen

    # --- Offene Posten -----------------------------------------------------

    @staticmethod
    def dokument_positionen(documents: list[Document], heute: date, bis: date, terms_days: int) -> list[Position]:
        """Offene Rechnungen als erwarteter Geldfluss.

        Was schon überfällig ist, wird auf *heute* gelegt statt in die
        Vergangenheit: es ist Geld, das noch bewegt werden muss.
        """
        positionen: list[Position] = []
        for doc in documents:
            faellig = effective_due_date(doc, terms_days) or heute
            ueberfaellig = faellig < heute
            wann = heute if ueberfaellig else faellig
            if wann > bis:
                continue
            betrag = chf(abs(float(doc.amount or 0)))
            eingang = doc.direction == DIRECTION_AUSGANG  # unsere Rechnung → Kunde zahlt uns
            positionen.append(
                Position(
                    datum=wann,
                    label=doc.vendor or doc.filename or f"Beleg {doc.id}",
                    betrag=betrag if eingang else -betrag,
                    quelle="debitor" if eingang else "kreditor",
                    document_id=doc.id,
                    ueberfaellig=ueberfaellig,
                )
            )
        return positionen

    # --- Steuer ------------------------------------------------------------

    @staticmethod
    def steuer(bookings: list[Booking], heute: date, satz: float | None) -> Steuer:
        """Gewinn seit Jahresbeginn und was davon zurückzulegen wäre.

        Der Steueraufwand selbst (8900) zählt **nicht** als Aufwand: sonst
        senkt jede Rückstellung den Gewinn, auf den die nächste gerechnet wird,
        und die Schätzung jagt sich selbst. Gerechnet wird auf dem Gewinn vor
        Steuern; der Bund rechnet seine 8.5 % zwar vom Gewinn *nach* Steuern,
        aber der effektive Satz, den der Treuhänder nennt, ist bereits auf den
        Gewinn vor Steuern umgerechnet.
        """
        ertrag = aufwand = zurueckgestellt = 0.0
        for b in bookings:
            d = parse_date(b.datum)
            if d is None or d.year != heute.year or d > heute:
                continue
            betrag = float(b.betrag or 0)
            # Ertrag steht im Haben, Aufwand im Soll.
            if (b.kt_haben or "").startswith(ERTRAG_PRAEFIX):
                ertrag += betrag
            if (b.kt_soll or "").startswith(ERTRAG_PRAEFIX):
                ertrag -= betrag
            if (b.kt_soll or "").startswith(AUFWAND_PRAEFIXE) and b.kt_soll != KONTO_STEUERAUFWAND:
                aufwand += betrag
            if (b.kt_haben or "").startswith(AUFWAND_PRAEFIXE) and b.kt_haben != KONTO_STEUERAUFWAND:
                aufwand -= betrag
            if (b.kt_haben or "") == KONTO_STEUERRUECKSTELLUNG:
                zurueckgestellt += betrag
            if (b.kt_soll or "") == KONTO_STEUERRUECKSTELLUNG:
                zurueckgestellt -= betrag

        ertrag = chf(ertrag)
        aufwand = chf(aufwand)
        gewinn = chf(ertrag - aufwand)
        zurueckgestellt = chf(zurueckgestellt)

        if satz is None:
            return Steuer(
                jahr=heute.year,
                ertrag=ertrag,
                aufwand=aufwand,
                gewinn=gewinn,
                satz=None,
                rueckstellung_soll=None,
                schon_zurueckgestellt=zurueckgestellt,
                offen=None,
                pro_quartal=None,
                hinweis=(
                    "Kein Gewinnsteuersatz hinterlegt. Die effektive Belastung hängt von Kanton "
                    "und Gemeinde ab — fragen Sie Ihren Treuhänder und tragen Sie den Satz im "
                    "Firmenprofil ein."
                ),
            )

        if gewinn <= 0:
            return Steuer(
                jahr=heute.year,
                ertrag=ertrag,
                aufwand=aufwand,
                gewinn=gewinn,
                satz=satz,
                rueckstellung_soll=0.0,
                schon_zurueckgestellt=zurueckgestellt,
                offen=0.0,
                pro_quartal=0.0,
                hinweis="Bisher kein Gewinn in diesem Jahr — nichts zurückzulegen.",
            )

        soll = chf(gewinn * satz / 100)
        offen = chf(max(soll - zurueckgestellt, 0.0))
        # Was bis Jahresende noch zur Seite muss, auf die verbleibenden Quartale verteilt.
        restquartale = max(4 - (heute.month - 1) // 3, 1)
        return Steuer(
            jahr=heute.year,
            ertrag=ertrag,
            aufwand=aufwand,
            gewinn=gewinn,
            satz=satz,
            rueckstellung_soll=soll,
            schon_zurueckgestellt=zurueckgestellt,
            offen=offen,
            pro_quartal=chf(offen / restquartale),
            hinweis=(
                "Schätzung auf dem Gewinn seit Jahresbeginn, keine Steuererklärung. "
                f"Buchung: {KONTO_STEUERAUFWAND} an {KONTO_STEUERRUECKSTELLUNG}."
            ),
        )

    # --- Report ------------------------------------------------------------

    async def report(self, heute: date | None = None) -> LiquiditaetReport:
        heute = heute or today_utc()
        bis = heute + timedelta(days=HORIZONT_TAGE)

        bookings = await self._bookings()
        documents = await self._open_documents()
        profile = await self._profile()
        terms = profile.zahlungsfrist_tage if profile else DEFAULT_TERMS_DAYS
        satz = getattr(profile, "gewinnsteuer_satz", None) if profile else None

        stand = self.kontostand(bookings)
        dauer = self.dauerbuchungen(bookings, heute)
        positionen = self.dokument_positionen(documents, heute, bis, terms)
        positionen += self.dauer_positionen(dauer, heute, bis)
        positionen.sort(key=lambda p: (p.datum, -p.betrag))

        eingang = chf(sum(p.betrag for p in positionen if p.betrag > 0))
        ausgang = chf(-sum(p.betrag for p in positionen if p.betrag < 0))

        # Laufender Saldo: der tiefste Punkt ist die Zahl, die weh tut.
        laufend = stand
        tiefster, tiefster_am = stand, heute
        pro_monat: dict[str, Monat] = {}
        for p in positionen:
            laufend = chf(laufend + p.betrag)
            if laufend < tiefster:
                tiefster, tiefster_am = laufend, p.datum
            key = monatsschluessel(p.datum)
            monat = pro_monat.get(key)
            if monat is None:
                monat = Monat(schluessel=key, label=monatslabel(p.datum), eingang=0.0, ausgang=0.0, saldo_ende=laufend)
                pro_monat[key] = monat
            if p.betrag > 0:
                monat.eingang = chf(monat.eingang + p.betrag)
            else:
                monat.ausgang = chf(monat.ausgang - p.betrag)
            monat.saldo_ende = laufend

        warnungen: list[str] = []
        if not any(_liquide(b.kt_soll) or _liquide(b.kt_haben) for b in bookings):
            warnungen.append(
                "Keine Buchung auf Kasse oder Bank — der Kontostand ist 0.00 und die Prognose "
                "zeigt nur die Bewegungen, nicht das Guthaben."
            )
        else:
            warnungen.append(
                "Der Kontostand ist die Summe der hier gebuchten Bewegungen. Ohne erfasste "
                "Eröffnungsbilanz fehlt der Anfangsbestand."
            )
        if tiefster < 0:
            warnungen.append(
                f"Die Prognose rutscht am {tiefster_am.strftime('%d.%m.%Y')} unter null "
                f"({tiefster:.2f}). Prüfen Sie Zahlungsziele und offene Debitoren."
            )
        if not documents:
            warnungen.append("Keine offenen Rechnungen erfasst — die Prognose kennt nur die Dauerbuchungen.")

        return LiquiditaetReport(
            stichtag=heute,
            bis=bis,
            stand_heute=stand,
            eingang=eingang,
            ausgang=ausgang,
            prognose=chf(stand + eingang - ausgang),
            tiefster_stand=tiefster,
            tiefster_am=tiefster_am,
            positionen=positionen,
            dauerbuchungen=dauer,
            monate=[pro_monat[k] for k in sorted(pro_monat)],
            warnungen=warnungen,
            steuer=self.steuer(bookings, heute, satz),
        )


def now_utc() -> datetime:
    return datetime.now(UTC)
