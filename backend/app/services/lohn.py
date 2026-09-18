"""Gross-to-net for a Swiss monthly payroll (B-72).

Pure arithmetic: no database, no I/O. Give it an employee, a settings row and a
period, and it returns every line of the payslip with the rate that produced it.

Three rules the rest of the system depends on:

1. **It refuses rather than guesses.** A rate that is not on file is not zero.
   ``fehlende_konfiguration`` lists what is missing and ``berechnen`` raises
   ``LohnKonfigurationFehlt``. An estimated UVG premium would look like a
   payslip and be wrong in a way nobody notices until the Ausgleichskasse's
   yearly reconciliation.
2. **Optional insurances are allowed to be absent.** UVGZ and KTG are voluntary;
   ``None`` there means "not insured", not "unknown". That is the one place a
   missing number legitimately means no deduction, and it is why those fields
   are separate from the compulsory ones.
3. **The ALV ceiling is cumulative.** The limit is annual, so the caller passes
   the gross already paid this year and the cap is applied to the running total.
   A per-month twelfth would mis-deduct in any month with a 13th salary or a
   bonus and only come right at the year-end reconciliation.

What this module does not do, and cannot: Quellensteuer *tariffs* (cantonal
tables, per Tarifcode and civil status — the rate comes in per employee),
BVG Altersgutschriften (the pension fund's own plan decides; the amount comes
in per employee), and Swissdec ELM transmission (a certification, not a format).
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date

from app.models.lohn_settings import LohnSettings
from app.models.mitarbeiter import Mitarbeiter
from app.services.export import round_chf

# BVG-Schwellenwerte (BVV 2). Used only to notice that an employee *ought* to be
# insured while no amount is on file — never to compute a contribution.
BVG_EINTRITTSSCHWELLE = 22_680.0

# The Swiss payroll month is 30 days regardless of the calendar, so a half month
# is half a salary in February as well as in March.
TAGE_PRO_MONAT = 30
MONATE_PRO_JAHR = 12


class LohnKonfigurationFehlt(ValueError):
    """A rate the payslip needs is not on file. ``.fehlend`` names them."""

    def __init__(self, fehlend: list[str]):
        self.fehlend = fehlend
        super().__init__("Lohnkonfiguration unvollständig: " + ", ".join(fehlend))


@dataclass(frozen=True)
class Abzug:
    """One line of the payslip: what it is, at which rate, on which base."""

    label: str
    satz: float
    basis: float
    betrag: float


@dataclass(frozen=True)
class Lohnlauf:
    jahr: int
    monat: int
    anteil: float  # 1.0 for a full month, less when the employee joined or left
    grundlohn: float
    dreizehnter: float
    zulagen: float  # AHV-pflichtig
    kinderzulagen: float  # AHV-frei (B-96)
    ahv_lohn: float  # massgebender Lohn: the base every percentage is taken on
    brutto: float  # ahv_lohn + kinderzulagen: what the employee is paid
    abzuege: list[Abzug] = field(default_factory=list)
    abzuege_total: float = 0.0
    netto: float = 0.0
    arbeitgeber: list[Abzug] = field(default_factory=list)
    ag_total: float = 0.0

    @property
    def periode(self) -> str:
        return f"{self.jahr:04d}-{self.monat:02d}"


def _chf(value: float) -> float:
    return float(round_chf(value))


def _prozent(basis: float, satz: float) -> float:
    return _chf(basis * satz / 100.0)


def beschaeftigte_tage(mitarbeiter: Mitarbeiter, jahr: int, monat: int) -> int:
    """Payroll days in this month, on the 30-day convention.

    Entry and exit day both count; a month the employee was not employed in at
    all is 0. The calendar length is irrelevant — a full February is 30 days.
    """
    erster = date(jahr, monat, 1)
    letzter = date(jahr, monat, monthrange(jahr, monat)[1])
    eintritt = mitarbeiter.eintritt
    austritt = mitarbeiter.austritt
    if eintritt and eintritt > letzter:
        return 0
    if austritt and austritt < erster:
        return 0

    von = max(eintritt, erster) if eintritt else erster
    bis = min(austritt, letzter) if austritt else letzter
    if von > bis:
        return 0
    if von == erster and bis == letzter:
        return TAGE_PRO_MONAT

    tag_von = min(von.day, TAGE_PRO_MONAT)
    tag_bis = min(bis.day, TAGE_PRO_MONAT)
    if bis == letzter:
        tag_bis = TAGE_PRO_MONAT
    return max(0, tag_bis - tag_von + 1)


def monatsanteil(mitarbeiter: Mitarbeiter, jahr: int, monat: int) -> float:
    return beschaeftigte_tage(mitarbeiter, jahr, monat) / TAGE_PRO_MONAT


def jahresanteil(mitarbeiter: Mitarbeiter, jahr: int) -> float:
    """Fraction of the year employed — the pro rata for a 13th salary."""
    tage = sum(beschaeftigte_tage(mitarbeiter, jahr, m) for m in range(1, MONATE_PRO_JAHR + 1))
    return tage / (TAGE_PRO_MONAT * MONATE_PRO_JAHR)


def fehlende_settings(settings: LohnSettings) -> list[str]:
    """Compulsory tenant-level rates that are not on file, in payslip order.

    Only the ones that always apply. UVGZ and KTG are voluntary and their
    absence is an answer, not a gap — see the module docstring.
    """
    fehlend: list[str] = []
    if settings.uvg_nbu_satz is None:
        fehlend.append("UVG NBU-Satz")
    if settings.uvg_bu_satz is None:
        fehlend.append("UVG BU-Satz")
    if settings.fak_satz is None:
        fehlend.append("FAK-Satz")
    if settings.verwaltungskosten_satz is None:
        fehlend.append("Verwaltungskostenbeitrag")
    return fehlend


def fehlende_konfiguration(mitarbeiter: Mitarbeiter, settings: LohnSettings, *, jahresbrutto: float) -> list[str]:
    """Rates this payslip needs and does not have, in payslip order.

    ``jahresbrutto`` is the employee's expected yearly gross; it decides only
    whether BVG is expected at all.
    """
    fehlend = fehlende_settings(settings)
    if mitarbeiter.quellensteuer and mitarbeiter.quellensteuer_satz is None:
        fehlend.append("Quellensteuersatz")
    if jahresbrutto >= BVG_EINTRITTSSCHWELLE and mitarbeiter.bvg_an_monat is None:
        fehlend.append("BVG-Beitrag (Arbeitnehmer)")
    if jahresbrutto >= BVG_EINTRITTSSCHWELLE and mitarbeiter.bvg_ag_monat is None:
        fehlend.append("BVG-Beitrag (Arbeitgeber)")
    return fehlend


def berechnen(
    *,
    mitarbeiter: Mitarbeiter,
    settings: LohnSettings,
    jahr: int,
    monat: int,
    zulagen: float = 0.0,
    dreizehnter: bool = False,
    brutto_ytd: float = 0.0,
) -> Lohnlauf:
    """One month's payslip.

    ``brutto_ytd`` is the gross already paid to this employee in ``jahr`` before
    this run; it is what makes the ALV ceiling cumulative. ``dreizehnter`` asks
    for the 13th salary to be paid out with this month, pro rata temporis.
    """
    anteil = monatsanteil(mitarbeiter, jahr, monat)
    grundlohn = _chf(mitarbeiter.monatslohn * anteil)
    dreizehnter_betrag = (
        _chf(mitarbeiter.monatslohn * jahresanteil(mitarbeiter, jahr))
        if dreizehnter and mitarbeiter.dreizehnter
        else 0.0
    )
    zulagen = _chf(zulagen)
    # B-96: two different sums, and the payslip the owner brought to the first
    # real run showed exactly this split — Bruttolohn 6'657.95, every deduction
    # on 6'257.95. Familienzulagen are not massgebender Lohn (AHVV Art. 6):
    # they are paid out, they are taxable, and no social insurance rate touches
    # them. Before this, `brutto` was both numbers at once and the AHV, ALV,
    # NBU, KTG, FAK and VK were all overstated by the Zulage — 400 × 5.3 % =
    # 21.20 too much AHV alone, every month, silently.
    # `or 0.0` like bvg_an_monat above: a column default applies on INSERT, not
    # to an object built in Python, so a fresh Mitarbeiter carries None here.
    kinderzulagen = _chf((mitarbeiter.kinderzulagen_monat or 0.0) * anteil)
    ahv_lohn = _chf(grundlohn + dreizehnter_betrag + zulagen)
    brutto = _chf(ahv_lohn + kinderzulagen)

    jahresbrutto = _chf(brutto_ytd + ahv_lohn + mitarbeiter.monatslohn * (MONATE_PRO_JAHR - monat))
    fehlend = fehlende_konfiguration(mitarbeiter, settings, jahresbrutto=jahresbrutto)
    if fehlend:
        raise LohnKonfigurationFehlt(fehlend)

    # --- Arbeitnehmer -----------------------------------------------------
    abzuege: list[Abzug] = []
    ahv = _prozent(ahv_lohn, settings.ahv_satz_an)
    abzuege.append(Abzug("AHV/IV/EO", settings.ahv_satz_an, ahv_lohn, ahv))

    alv_basis = max(0.0, min(ahv_lohn, _chf(settings.alv_jahresgrenze - brutto_ytd)))
    alv = _prozent(alv_basis, settings.alv_satz_an)
    abzuege.append(Abzug("ALV", settings.alv_satz_an, alv_basis, alv))

    nbu = _prozent(ahv_lohn, settings.uvg_nbu_satz or 0.0)
    abzuege.append(Abzug("NBU", settings.uvg_nbu_satz or 0.0, ahv_lohn, nbu))

    uvgz = _prozent(ahv_lohn, settings.uvgz_satz_an) if settings.uvgz_satz_an else 0.0
    if uvgz:
        abzuege.append(Abzug("UVGZ", settings.uvgz_satz_an or 0.0, ahv_lohn, uvgz))
    ktg = _prozent(ahv_lohn, settings.ktg_satz_an) if settings.ktg_satz_an else 0.0
    if ktg:
        abzuege.append(Abzug("KTG", settings.ktg_satz_an or 0.0, ahv_lohn, ktg))

    # BVG is an amount from the fund, pro-rated like the salary when the month
    # is partial — the fund bills the month, the employee owes their share of it.
    bvg = _chf((mitarbeiter.bvg_an_monat or 0.0) * anteil)
    if bvg:
        abzuege.append(Abzug("BVG", 0.0, ahv_lohn, bvg))

    # Quellensteuer stays on `brutto`, deliberately: Familienzulagen are taxable
    # income — exempt from the social insurances, not from tax.
    quellensteuer = (
        _prozent(brutto, mitarbeiter.quellensteuer_satz or 0.0)
        if mitarbeiter.quellensteuer and mitarbeiter.quellensteuer_satz
        else 0.0
    )
    if quellensteuer:
        abzuege.append(Abzug("Quellensteuer", mitarbeiter.quellensteuer_satz or 0.0, brutto, quellensteuer))

    abzuege_total = _chf(sum(a.betrag for a in abzuege))
    netto = _chf(brutto - abzuege_total)

    # --- Arbeitgeber ------------------------------------------------------
    # AHV and ALV are paid in equal halves, so the employer share is the
    # employee's own rate applied to the same base.
    arbeitgeber: list[Abzug] = [
        Abzug("AHV/IV/EO", settings.ahv_satz_an, ahv_lohn, ahv),
        Abzug("ALV", settings.alv_satz_an, alv_basis, alv),
        Abzug("UVG BU", settings.uvg_bu_satz or 0.0, ahv_lohn, _prozent(ahv_lohn, settings.uvg_bu_satz or 0.0)),
    ]
    if settings.uvgz_satz_ag:
        arbeitgeber.append(Abzug("UVGZ", settings.uvgz_satz_ag, ahv_lohn, _prozent(ahv_lohn, settings.uvgz_satz_ag)))
    if settings.ktg_satz_ag:
        arbeitgeber.append(Abzug("KTG", settings.ktg_satz_ag, ahv_lohn, _prozent(ahv_lohn, settings.ktg_satz_ag)))
    arbeitgeber.append(Abzug("FAK", settings.fak_satz or 0.0, ahv_lohn, _prozent(ahv_lohn, settings.fak_satz or 0.0)))
    arbeitgeber.append(
        Abzug(
            "Verwaltungskosten",
            settings.verwaltungskosten_satz or 0.0,
            ahv_lohn,
            _prozent(ahv_lohn, settings.verwaltungskosten_satz or 0.0),
        )
    )
    ag_bvg = _chf((mitarbeiter.bvg_ag_monat or 0.0) * anteil)
    if ag_bvg:
        arbeitgeber.append(Abzug("BVG", 0.0, ahv_lohn, ag_bvg))
    ag_total = _chf(sum(a.betrag for a in arbeitgeber))

    return Lohnlauf(
        jahr=jahr,
        monat=monat,
        anteil=anteil,
        grundlohn=grundlohn,
        dreizehnter=dreizehnter_betrag,
        zulagen=zulagen,
        kinderzulagen=kinderzulagen,
        ahv_lohn=ahv_lohn,
        brutto=brutto,
        abzuege=abzuege,
        abzuege_total=abzuege_total,
        netto=netto,
        arbeitgeber=arbeitgeber,
        ag_total=ag_total,
    )


def abzug(lauf: Lohnlauf, label: str) -> Abzug | None:
    """The employee deduction with this label, or None if it did not apply."""
    return next((a for a in lauf.abzuege if a.label == label), None)


def ag_beitrag(lauf: Lohnlauf, label: str) -> Abzug | None:
    return next((a for a in lauf.arbeitgeber if a.label == label), None)
