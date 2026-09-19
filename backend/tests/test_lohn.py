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
        "lohnart": "monat",
        "monatslohn": 6_000.0,
        "stundenlohn": 0.0,
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


# --- B-96: Kinderzulagen are paid, taxed, and exempt from every rate ---------
#
# The payslip the owner brought to the first real run (June 2026): Monatslohn
# 6'257.95, Kinderzulagen 400, Bruttolohn 6'657.95 — and every deduction on
# 6'257.95. Ours took them on 6'657.95. Familienzulagen are not massgebender
# Lohn (AHVV Art. 6). These tests hold the split.


def _kz():
    # The June payslip: PK 9.9 % of 6'257.95 = 619.54 on the employee side.
    return mitarbeiter(monatslohn=6_257.95, kinderzulagen_monat=400.0, bvg_an_monat=619.54, bvg_ag_monat=619.54)


def test_kinderzulagen_are_paid_out_but_not_in_the_ahv_base():
    lauf = berechnen(mitarbeiter=_kz(), settings=settings(uvg_nbu_satz=0.5, ktg_satz_an=0.7), jahr=2026, monat=6)
    assert lauf.kinderzulagen == 400.0
    assert lauf.ahv_lohn == 6_257.95
    assert lauf.brutto == 6_657.95  # what the employee is paid, Zulage included
    for label in ("AHV/IV/EO", "ALV", "NBU", "KTG"):
        assert abzug(lauf, label).basis == 6_257.95, label


def test_the_owners_june_payslip_to_the_rappen():
    """The real numbers, line by line. The old provider does not round at all
    (its net was 5562.80875); we round half-up per line, which is the only
    version that can be paid. The difference is under one Rappen."""
    lauf = berechnen(mitarbeiter=_kz(), settings=settings(uvg_nbu_satz=0.5, ktg_satz_an=0.7), jahr=2026, monat=6)
    assert abzug(lauf, "AHV/IV/EO").betrag == 331.67  # 6257.95 × 5.3 %
    assert abzug(lauf, "ALV").betrag == 68.84  # × 1.1 %
    assert abzug(lauf, "NBU").betrag == 31.29  # × 0.5 %
    assert abzug(lauf, "KTG").betrag == 43.81  # × 0.7 %
    assert abzug(lauf, "BVG").betrag == 619.54  # the fund's amount, not a rate
    assert lauf.abzuege_total == 1_095.15  # theirs: 1095.14125, unrounded
    assert lauf.netto == 5_562.80  # theirs: 5562.80875 — under one Rappen apart


def test_every_employer_rate_also_skips_the_kinderzulagen():
    lauf = berechnen(mitarbeiter=_kz(), settings=settings(), jahr=2026, monat=6)
    for label in ("AHV/IV/EO", "UVG BU", "FAK", "Verwaltungskosten"):
        assert ag_beitrag(lauf, label).basis == 6_257.95, label


def test_kinderzulagen_stay_in_the_quellensteuer_base():
    """Exempt from the social insurances, not from tax."""
    person = _kz()
    person.quellensteuer, person.quellensteuer_satz = True, 10.0
    lauf = berechnen(mitarbeiter=person, settings=settings(), jahr=2026, monat=6)
    assert abzug(lauf, "Quellensteuer").basis == 6_657.95


def test_a_partial_month_pro_rates_the_kinderzulagen_too():
    person = _kz()
    person.eintritt = date(2026, 6, 16)  # half of a 30-day payroll month
    lauf = berechnen(mitarbeiter=person, settings=settings(), jahr=2026, monat=6)
    assert lauf.kinderzulagen == 200.0
    assert lauf.ahv_lohn == pytest.approx(6_257.95 / 2, abs=0.01)


def test_an_ahv_liable_zulage_is_still_in_the_base():
    """The one-off Zulage (Gratifikation, Bonus) is the other kind — it stays
    contributory. The two fields must not be confused for each other."""
    lauf = berechnen(mitarbeiter=_kz(), settings=settings(), jahr=2026, monat=6, zulagen=500.0)
    assert lauf.zulagen == 500.0
    assert lauf.ahv_lohn == 6_757.95  # 6257.95 + 500, Kinderzulagen not included
    assert lauf.brutto == 7_157.95  # + 400 Kinderzulagen
    assert abzug(lauf, "AHV/IV/EO").basis == 6_757.95


def test_no_kinderzulagen_changes_nothing():
    """Every existing test above still holds — a tenant without Zulagen sees
    the same payslip as before B-96."""
    lauf = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    assert lauf.kinderzulagen == 0.0
    assert lauf.ahv_lohn == lauf.brutto == 6_000.0


# --- B-100: paid by the hour ------------------------------------------------
#
# The design in one line: an hourly wage changes *how the gross is arrived at*
# and nothing else. Everything after the Grundlohn — AHV, ALV, the ALV ceiling,
# the UVG premiums, the Familienzulagen, the employer side — is the same code
# and must stay the same numbers.


def stuendlich(**over) -> Mitarbeiter:
    values = {"lohnart": "stunde", "stundenlohn": 32.50, "monatslohn": 0.0}
    values.update(over)
    return mitarbeiter(**values)


def test_the_gross_is_hours_times_rate():
    lauf = berechnen(mitarbeiter=stuendlich(), settings=settings(), jahr=2026, monat=3, stunden=120.0)
    assert lauf.grundlohn == 3_900.0  # 120 × 32.50
    assert lauf.stunden == 120.0
    assert lauf.stundenlohn == 32.50
    assert lauf.brutto == 3_900.0


def test_the_same_deductions_apply_as_for_a_monthly_salary():
    """The whole point of the split: only the Grundlohn line differs."""
    stunde = berechnen(mitarbeiter=stuendlich(stundenlohn=50.0), settings=settings(), jahr=2026, monat=3, stunden=120.0)
    monat = berechnen(mitarbeiter=mitarbeiter(monatslohn=6_000.0), settings=settings(), jahr=2026, monat=3)

    assert stunde.brutto == monat.brutto == 6_000.0
    assert stunde.ahv_lohn == monat.ahv_lohn
    assert [(a.label, a.betrag) for a in stunde.abzuege] == [(a.label, a.betrag) for a in monat.abzuege]
    assert stunde.netto == monat.netto
    assert stunde.ag_total == monat.ag_total


def test_a_part_month_is_not_counted_twice():
    """Joining mid-month already shows up in the hours; `anteil` must not cut them again."""
    person = stuendlich(eintritt=date(2026, 3, 16))
    lauf = berechnen(mitarbeiter=person, settings=settings(), jahr=2026, monat=3, stunden=60.0)
    assert lauf.anteil < 1.0  # the month really is partial
    assert lauf.grundlohn == 1_950.0  # 60 × 32.50, not half of that


def test_kinderzulagen_are_still_pro_rated_by_the_month():
    """They are a monthly entitlement, not an hourly one — B-96's rule is untouched."""
    person = stuendlich(kinderzulagen_monat=400.0, eintritt=date(2026, 3, 16))
    lauf = berechnen(mitarbeiter=person, settings=settings(), jahr=2026, monat=3, stunden=60.0)
    assert lauf.kinderzulagen == 200.0  # half a month
    assert lauf.ahv_lohn == 1_950.0  # and still outside every rate's base
    assert lauf.brutto == 2_150.0


def test_no_hours_is_a_valid_month():
    """Nobody worked. That is a payslip of zero, not an error."""
    lauf = berechnen(
        mitarbeiter=stuendlich(bvg_an_monat=None, bvg_ag_monat=None),
        settings=settings(),
        jahr=2026,
        monat=1,
        stunden=0.0,
    )
    assert lauf.grundlohn == 0.0
    assert lauf.brutto == 0.0
    assert lauf.netto == 0.0


def test_negative_hours_cannot_reduce_a_salary():
    lauf = berechnen(
        mitarbeiter=stuendlich(bvg_an_monat=None, bvg_ag_monat=None),
        settings=settings(),
        jahr=2026,
        monat=1,
        stunden=-40.0,
    )
    assert lauf.grundlohn == 0.0


def test_a_missing_hourly_rate_is_refused_not_treated_as_zero():
    """Same rule as a missing UVG premium — a payslip of 0.00 looks like a real one."""
    with pytest.raises(LohnKonfigurationFehlt) as exc:
        berechnen(mitarbeiter=stuendlich(stundenlohn=0.0), settings=settings(), jahr=2026, monat=3, stunden=120.0)
    assert "Stundenlohn" in exc.value.fehlend


def test_the_thirteenth_is_not_invented_for_hourly_work():
    """A 13th for hourly work is a percentage supplement on each payslip, which is a
    different agreement with a different base. Paying a monthly salary that does not
    exist would be worse than paying nothing."""
    person = stuendlich(dreizehnter=True, monatslohn=6_000.0)
    lauf = berechnen(mitarbeiter=person, settings=settings(), jahr=2026, monat=12, stunden=120.0, dreizehnter=True)
    assert lauf.dreizehnter == 0.0
    assert lauf.brutto == 3_900.0


def test_hours_do_not_touch_the_monthly_employee():
    """A stray `stunden` on a monthly payslip must change nothing."""
    ohne = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3)
    mit = berechnen(mitarbeiter=mitarbeiter(), settings=settings(), jahr=2026, monat=3, stunden=999.0)
    assert (mit.brutto, mit.netto, mit.stunden, mit.stundenlohn) == (ohne.brutto, ohne.netto, 0.0, 0.0)


def test_the_alv_ceiling_still_accumulates_across_hourly_months():
    """The cap is annual and reads `brutto_ytd`; nothing about it is monthly."""
    person = stuendlich(stundenlohn=1_000.0)
    lauf = berechnen(mitarbeiter=person, settings=settings(), jahr=2026, monat=12, stunden=20.0, brutto_ytd=140_000.0)
    alv = abzug(lauf, "ALV")
    assert alv.basis == 8_200.0  # 148'200 − 140'000, not the full 20'000
