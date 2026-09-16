"""The BVG minimum, as a check (B-72, option C).

Everything here is federal law read out of one table, so the tests are mostly
arithmetic against figures that can be looked up. The two that are not:
`grenzen_fuer` must never extrapolate, and Art. 66 is a workforce comparison,
not a per-person one.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.mitarbeiter import Mitarbeiter
from app.services.bvg import (
    AELTESTES_JAHR,
    ALTERSGUTSCHRIFTEN,
    GRENZBETRAEGE,
    JUENGSTES_JAHR,
    altersgutschrift_satz,
    altersjahr,
    grenzen_fuer,
    koordinierter_lohn,
    mindest_altersgutschrift_jahr,
    pruefen,
)

G2026 = GRENZBETRAEGE[2026]


def mitarbeiter(**over) -> Mitarbeiter:
    """`pruefen` is pure, so nothing here needs a database."""
    values = {
        "id": 1,
        "vorname": "Anna",
        "name": "Muster",
        "monatslohn": 6_000.0,
        "dreizehnter": False,
        "geburtsdatum": date(1986, 5, 4),
        "bvg_an_monat": 300.0,
        "bvg_ag_monat": 300.0,
    }
    values.update(over)
    return Mitarbeiter(**values)


# --------------------------------------------------------------------------- #
# The table itself
# --------------------------------------------------------------------------- #


def test_the_years_are_contiguous():
    """A gap would silently send one year to the wrong figures."""
    assert sorted(GRENZBETRAEGE) == list(range(AELTESTES_JAHR, JUENGSTES_JAHR + 1))


def test_every_year_is_internally_consistent():
    for jahr, g in GRENZBETRAEGE.items():
        assert g.jahr == jahr
        assert g.obere_limite > g.koordinationsabzug > g.eintrittsschwelle > g.min_koordinierter_lohn > 0, jahr


def test_the_2026_figures_are_the_published_ones():
    """BSV, «Beträge gültig ab dem 1. Januar 2026»."""
    assert (G2026.eintrittsschwelle, G2026.koordinationsabzug, G2026.min_koordinierter_lohn, G2026.obere_limite) == (
        22_680.0,
        26_460.0,
        3_780.0,
        90_720.0,
    )


def test_the_rates_are_art_16_bvg():
    assert ALTERSGUTSCHRIFTEN == ((25, 7.0), (35, 10.0), (45, 15.0), (55, 18.0))


def test_a_future_year_uses_the_newest_table_and_says_so():
    grenzen, aktuell = grenzen_fuer(JUENGSTES_JAHR + 3)
    assert grenzen.jahr == JUENGSTES_JAHR
    assert aktuell is False, "the caller has to be able to put that on screen"


def test_a_year_before_the_table_is_also_flagged():
    grenzen, aktuell = grenzen_fuer(AELTESTES_JAHR - 1)
    assert grenzen.jahr == AELTESTES_JAHR
    assert aktuell is False


def test_a_known_year_is_reported_as_current():
    grenzen, aktuell = grenzen_fuer(2024)
    assert grenzen.jahr == 2024
    assert aktuell is True


def test_the_2005_break_is_why_nothing_is_interpolated():
    """Before 2005 the Eintrittsschwelle equalled the Koordinationsabzug; after, it did not.
    Any rule that derives one from the other would have been wrong on one side of that year."""
    assert GRENZBETRAEGE[2026].eintrittsschwelle != GRENZBETRAEGE[2026].koordinationsabzug


# --------------------------------------------------------------------------- #
# Age
# --------------------------------------------------------------------------- #


def test_the_age_band_changes_at_new_year_not_at_the_birthday():
    """Art. 16 counts Altersjahre — calendar year minus year of birth."""
    dezember = date(2000, 12, 31)
    januar = date(2000, 1, 1)
    assert altersjahr(dezember, 2026) == altersjahr(januar, 2026) == 26


def test_no_birthday_means_no_age():
    assert altersjahr(None, 2026) is None


@pytest.mark.parametrize(
    ("alter", "satz"),
    [
        (18, 0.0),
        (24, 0.0),
        (25, 7.0),
        (34, 7.0),
        (35, 10.0),
        (44, 10.0),
        (45, 15.0),
        (54, 15.0),
        (55, 18.0),
        (70, 18.0),
    ],
)
def test_the_rate_for_each_age(alter, satz):
    assert altersgutschrift_satz(alter) == satz


def test_an_unknown_age_saves_nothing_rather_than_guessing():
    assert altersgutschrift_satz(None) == 0.0


# --------------------------------------------------------------------------- #
# Koordinierter Lohn
# --------------------------------------------------------------------------- #


def test_below_the_entry_threshold_nothing_is_insured():
    assert koordinierter_lohn(G2026.eintrittsschwelle - 1, G2026) == 0.0


def test_at_the_entry_threshold_the_minimum_applies_not_a_negative_number():
    """22'680 − 26'460 is negative; the law floors it at the minimum."""
    assert koordinierter_lohn(G2026.eintrittsschwelle, G2026) == G2026.min_koordinierter_lohn


def test_an_ordinary_salary_is_salary_minus_the_deduction():
    assert koordinierter_lohn(80_000.0, G2026) == 80_000.0 - 26_460.0


def test_above_the_upper_limit_the_salary_is_capped():
    assert koordinierter_lohn(250_000.0, G2026) == 90_720.0 - 26_460.0
    assert koordinierter_lohn(250_000.0, G2026) == 64_260.0, "the published maximum koordinierter Lohn for 2026"


# --------------------------------------------------------------------------- #
# The minimum
# --------------------------------------------------------------------------- #


def test_the_minimum_for_a_worked_example():
    # 80'000 salary, age 40 in 2026: (80'000 − 26'460) × 10 % = 5'354.00
    assert mindest_altersgutschrift_jahr(80_000.0, 40, G2026) == 5_354.0


def test_someone_under_25_has_no_savings_obligation():
    assert mindest_altersgutschrift_jahr(80_000.0, 24, G2026) == 0.0


def test_someone_below_the_threshold_has_none_either():
    assert mindest_altersgutschrift_jahr(10_000.0, 40, G2026) == 0.0


# --------------------------------------------------------------------------- #
# The check
# --------------------------------------------------------------------------- #


def test_a_compliant_plan_produces_no_findings():
    person = mitarbeiter(monatslohn=6_666.67, bvg_an_monat=230.0, bvg_ag_monat=230.0)

    assert pruefen([person], 2026) == []


def test_a_contribution_below_the_obligation_is_reported():
    person = mitarbeiter(monatslohn=6_666.67, bvg_an_monat=10.0, bvg_ag_monat=10.0)

    assert [h.code for h in pruefen([person], 2026)] == ["unter_obligatorium"]


def test_the_finding_names_the_numbers_it_used():
    person = mitarbeiter(monatslohn=6_666.67, bvg_an_monat=10.0, bvg_ag_monat=10.0)

    text = pruefen([person], 2026)[0].text

    assert "10 %" in text
    assert "Altersjahr 40" in text


def test_the_finding_points_at_the_person():
    person = mitarbeiter(id=42, monatslohn=6_666.67, bvg_an_monat=10.0, bvg_ag_monat=10.0)

    assert pruefen([person], 2026)[0].mitarbeiter_id == 42


def test_nothing_is_reported_for_someone_under_the_threshold():
    person = mitarbeiter(monatslohn=800.0, bvg_an_monat=None, bvg_ag_monat=None)

    assert pruefen([person], 2026) == []


def test_a_missing_birthday_is_reported_rather_than_guessed():
    person = mitarbeiter(monatslohn=6_666.67, geburtsdatum=None)

    assert [h.code for h in pruefen([person], 2026)] == ["geburtsdatum_fehlt"]


def test_a_missing_birthday_below_the_threshold_is_not_worth_saying():
    person = mitarbeiter(monatslohn=800.0, geburtsdatum=None, bvg_an_monat=None, bvg_ag_monat=None)

    assert pruefen([person], 2026) == []


def test_the_thirteenth_salary_counts_towards_the_insured_salary():
    """A 13th pushes the yearly salary over the threshold; ignoring it would
    under-insure exactly the people closest to the line."""
    knapp = mitarbeiter(monatslohn=1_800.0, dreizehnter=True, bvg_an_monat=None, bvg_ag_monat=None)

    assert 1_800.0 * 12 < G2026.eintrittsschwelle <= 1_800.0 * 13
    assert [h.code for h in pruefen([knapp], 2026)] == ["unter_obligatorium"]


def test_art_66_is_checked_across_the_workforce_not_per_person():
    """One employee paying more than their own employer share is legal; the
    comparison the law makes is over the totals."""
    viel_an = mitarbeiter(id=1, monatslohn=7_000.0, bvg_an_monat=400.0, bvg_ag_monat=100.0)
    viel_ag = mitarbeiter(id=2, monatslohn=7_000.0, bvg_an_monat=100.0, bvg_ag_monat=400.0)

    codes = [h.code for h in pruefen([viel_an, viel_ag], 2026)]

    assert "arbeitgeber_unter_haelfte" not in codes


def test_an_employer_paying_less_than_half_in_total_is_reported():
    a = mitarbeiter(id=1, monatslohn=7_000.0, bvg_an_monat=400.0, bvg_ag_monat=100.0)
    b = mitarbeiter(id=2, monatslohn=7_000.0, bvg_an_monat=400.0, bvg_ag_monat=100.0)

    assert "arbeitgeber_unter_haelfte" in [h.code for h in pruefen([a, b], 2026)]


def test_an_exactly_equal_split_is_not_a_finding():
    person = mitarbeiter(monatslohn=7_000.0, bvg_an_monat=300.0, bvg_ag_monat=300.0)

    assert "arbeitgeber_unter_haelfte" not in [h.code for h in pruefen([person], 2026)]


def test_an_unknown_year_says_which_figures_it_used():
    person = mitarbeiter(monatslohn=7_000.0, bvg_an_monat=300.0, bvg_ag_monat=300.0)

    hinweise = pruefen([person], JUENGSTES_JAHR + 2)

    assert hinweise[0].code == "grenzbetraege_veraltet"
    assert str(JUENGSTES_JAHR) in hinweise[0].text


def test_an_empty_workforce_is_not_a_finding():
    assert pruefen([], 2026) == []
