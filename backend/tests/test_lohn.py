"""B-72 — gross to net, and what happens when a rate is not on file.

The engine's contract is that it never invents a number. Most of these tests
are therefore about refusal: which missing rate stops a payslip, which missing
rate legitimately means "not insured", and what the caller is told either way.
The arithmetic tests exist to pin down the two places Swiss payroll is not
obvious — the 30-day month and the cumulative ALV ceiling.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.lohn_settings import LohnSettings
from app.models.mitarbeiter import Mitarbeiter
from app.services.lohn import (
    BVG_EINTRITTSSCHWELLE,
    LohnKonfigurationFehlt,
    abzug,
    ag_beitrag,
    berechnen,
    beschaeftigte_tage,
    fehlende_konfiguration,
    jahresanteil,
)


def settings(**over) -> LohnSettings:
    """A fully configured tenant. Column defaults only apply on INSERT, so the
    federal rates are spelled out here too."""
    values = {
        "ahv_satz_an": 5.3,
        "alv_satz_an": 1.1,
        "alv_jahresgrenze": 148_200.0,
        "uvg_bu_satz": 0.8,
        "uvg_nbu_satz": 1.6,
        "uvgz_satz_an": None,
        "uvgz_satz_ag": None,
        "ktg_satz_an": None,
        "ktg_satz_ag": None,
        "fak_satz": 1.2,
        "verwaltungskosten_satz": 0.15,
    }
    values.update(over)
    return LohnSettings(**values)


def mitarbeiter(**over) -> Mitarbeiter:
    values = {
        "vorname": "Anna",
        "name": "Muster",
        "monatslohn": 6_000.0,
        "pensum": 100.0,
        "dreizehnter": False,
        "kinder": 0,
        "quellensteuer": False,
        "quellensteuer_satz": None,
        "bvg_an_monat": 300.0,
        "bvg_ag_monat": 300.0,
        "eintritt": date(2020, 1, 1),
        "austritt": None,
    }
    values.update(over)
    return Mitarbeiter(**values)


# --- the ordinary case ----------------------------------------------------


def test_a_full_month_deducts_the_federal_rates():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert lauf.brutto == 6_000.0
    assert abzug(lauf, "AHV/IV/EO").betrag == 318.0  # 5.3 %
    assert abzug(lauf, "ALV").betrag == 66.0  # 1.1 %
    assert abzug(lauf, "NBU").betrag == 96.0  # 1.6 %


def test_net_is_gross_minus_every_deduction():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert lauf.abzuege_total == pytest.approx(sum(a.betrag for a in lauf.abzuege))
    assert lauf.netto == pytest.approx(lauf.brutto - lauf.abzuege_total)


def test_every_deduction_carries_its_rate_and_base():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    ahv = abzug(lauf, "AHV/IV/EO")
    assert (ahv.satz, ahv.basis) == (5.3, 6_000.0)


def test_the_employer_pays_the_same_ahv_and_alv():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert ag_beitrag(lauf, "AHV/IV/EO").betrag == abzug(lauf, "AHV/IV/EO").betrag
    assert ag_beitrag(lauf, "ALV").betrag == abzug(lauf, "ALV").betrag


def test_the_employer_total_sums_its_lines():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert lauf.ag_total == pytest.approx(sum(a.betrag for a in lauf.arbeitgeber))


def test_bu_is_the_employers_alone():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert ag_beitrag(lauf, "UVG BU").betrag == 48.0  # 0.8 %
    assert abzug(lauf, "UVG BU") is None


def test_rounding_is_half_up_per_line():
    # 100.10 at 5 % is 5.005 — half-even or a binary round would give 5.00.
    lauf = berechnen(
        mitarbeiter=mitarbeiter(monatslohn=100.10, bvg_an_monat=0.0, bvg_ag_monat=0.0),
        settings=settings(ahv_satz_an=5.0),
        jahr=2026,
        monat=3,
    )
    assert abzug(lauf, "AHV/IV/EO").betrag == 5.01


# --- refusal --------------------------------------------------------------


def test_a_missing_nbu_rate_stops_the_payslip():
    with pytest.raises(LohnKonfigurationFehlt) as exc:
        berechnen(mitarbeiter=mitarbeiter(), settings=settings(uvg_nbu_satz=None), jahr=2026, monat=3)
    assert "UVG NBU-Satz" in exc.value.fehlend


def test_every_missing_rate_is_named_at_once():
    fehlend = fehlende_konfiguration(
        mitarbeiter(),
        settings(uvg_bu_satz=None, uvg_nbu_satz=None, fak_satz=None, verwaltungskosten_satz=None),
        jahresbrutto=72_000.0,
    )
    assert fehlend == ["UVG NBU-Satz", "UVG BU-Satz", "FAK-Satz", "Verwaltungskostenbeitrag"]


def test_quellensteuer_without_a_rate_is_refused():
    with pytest.raises(LohnKonfigurationFehlt) as exc:
        berechnen(
            mitarbeiter=mitarbeiter(quellensteuer=True, quellensteuer_satz=None),
            settings=settings(),
            jahr=2026,
            monat=3,
        )
    assert "Quellensteuersatz" in exc.value.fehlend


def test_a_salary_above_the_bvg_threshold_needs_an_amount():
    with pytest.raises(LohnKonfigurationFehlt) as exc:
        berechnen(
            mitarbeiter=mitarbeiter(bvg_an_monat=None, bvg_ag_monat=None),
            settings=settings(),
            jahr=2026,
            monat=1,
        )
    assert "BVG-Beitrag (Arbeitnehmer)" in exc.value.fehlend
    assert "BVG-Beitrag (Arbeitgeber)" in exc.value.fehlend


def test_a_salary_below_the_threshold_does_not():
    klein = BVG_EINTRITTSSCHWELLE / 12 - 100
    lauf = berechnen(
        mitarbeiter=mitarbeiter(monatslohn=klein, bvg_an_monat=None, bvg_ag_monat=None),
        settings=settings(),
        jahr=2026,
        monat=1,
    )
    assert abzug(lauf, "BVG") is None


def test_the_message_lists_what_is_missing():
    err = LohnKonfigurationFehlt(["FAK-Satz", "Quellensteuersatz"])
    assert "FAK-Satz" in str(err) and "Quellensteuersatz" in str(err)


# --- optional insurances --------------------------------------------------


def test_uvgz_and_ktg_absent_means_not_insured_not_unknown():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert abzug(lauf, "UVGZ") is None
    assert abzug(lauf, "KTG") is None


def test_uvgz_and_ktg_are_deducted_when_configured():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(),
        settings=settings(uvgz_satz_an=0.5, uvgz_satz_ag=0.5, ktg_satz_an=0.7, ktg_satz_ag=0.7),
        jahr=2026,
        monat=3,
    )
    assert abzug(lauf, "UVGZ").betrag == 30.0
    assert abzug(lauf, "KTG").betrag == 42.0
    assert ag_beitrag(lauf, "UVGZ").betrag == 30.0


# --- the ALV ceiling ------------------------------------------------------


def test_alv_stops_once_the_annual_ceiling_is_reached():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(monatslohn=20_000.0),
        settings=settings(),
        jahr=2026,
        monat=9,
        brutto_ytd=148_200.0,
    )
    assert abzug(lauf, "ALV").basis == 0.0
    assert abzug(lauf, "ALV").betrag == 0.0


def test_the_month_that_crosses_the_ceiling_is_split():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(monatslohn=20_000.0),
        settings=settings(),
        jahr=2026,
        monat=8,
        brutto_ytd=140_000.0,
    )
    assert abzug(lauf, "ALV").basis == 8_200.0
    assert abzug(lauf, "ALV").betrag == pytest.approx(90.20)


def test_ahv_has_no_ceiling():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(monatslohn=20_000.0),
        settings=settings(),
        jahr=2026,
        monat=9,
        brutto_ytd=148_200.0,
    )
    assert abzug(lauf, "AHV/IV/EO").basis == 20_000.0


# --- the 30-day month -----------------------------------------------------


def test_a_full_february_is_thirty_days():
    assert beschaeftigte_tage(mitarbeiter(), 2026, 2) == 30


def test_joining_mid_month_is_half_a_salary():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(eintritt=date(2026, 3, 16)),
        settings=settings(),
        jahr=2026,
        monat=3,
    )
    assert lauf.anteil == pytest.approx(0.5)
    assert lauf.grundlohn == 3_000.0


def test_leaving_mid_month_is_half_a_salary():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(austritt=date(2026, 3, 15)),
        settings=settings(),
        jahr=2026,
        monat=3,
    )
    assert lauf.grundlohn == 3_000.0


def test_a_month_before_the_entry_date_pays_nothing():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(eintritt=date(2026, 7, 1), bvg_an_monat=0.0, bvg_ag_monat=0.0),
        settings=settings(),
        jahr=2026,
        monat=6,
    )
    assert lauf.brutto == 0.0
    assert lauf.netto == 0.0


def test_the_last_calendar_day_always_closes_the_month():
    # Leaving on 28 February is a whole month, not 28/30 of one.
    assert beschaeftigte_tage(mitarbeiter(austritt=date(2026, 2, 28)), 2026, 2) == 30


# --- 13th salary ----------------------------------------------------------


def test_the_thirteenth_is_pro_rata_for_a_part_year():
    ma = mitarbeiter(eintritt=date(2026, 7, 1), dreizehnter=True)
    assert jahresanteil(ma, 2026) == pytest.approx(0.5)
    lauf = berechnen(mitarbeiter=ma, settings=settings(), jahr=2026, monat=12, dreizehnter=True)
    assert lauf.dreizehnter == 3_000.0
    assert lauf.brutto == 9_000.0


def test_no_thirteenth_when_the_contract_has_none():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(dreizehnter=False),
        settings=settings(),
        jahr=2026,
        monat=12,
        dreizehnter=True,
    )
    assert lauf.dreizehnter == 0.0


def test_the_thirteenth_is_ahv_liable_like_any_other_salary():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(dreizehnter=True),
        settings=settings(),
        jahr=2026,
        monat=12,
        dreizehnter=True,
    )
    assert abzug(lauf, "AHV/IV/EO").basis == 12_000.0


# --- Zulagen and BVG ------------------------------------------------------


def test_zulagen_raise_the_gross_and_every_percentage_with_it():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3, zulagen=500.0)
    assert lauf.brutto == 6_500.0
    assert abzug(lauf, "AHV/IV/EO").betrag == pytest.approx(344.50)


def test_bvg_is_an_amount_not_a_rate():
    lauf = berechnen(mitarbeiter=mitarbeiter(bvg_an_monat=412.35), settings=settings(), jahr=2026, monat=3)
    assert abzug(lauf, "BVG").betrag == 412.35
    assert abzug(lauf, "BVG").satz == 0.0


def test_bvg_follows_a_part_month():
    lauf = berechnen(
        mitarbeiter=mitarbeiter(eintritt=date(2026, 3, 16), bvg_an_monat=300.0),
        settings=settings(),
        jahr=2026,
        monat=3,
    )
    assert abzug(lauf, "BVG").betrag == 150.0


def test_the_period_reads_as_a_month():
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert lauf.periode == "2026-03"
