"""B-72 — the comparison that lifts the watermark.

Every payslip this product prints says «Nicht für die Einreichung» until one
real month has been checked against the previous provider. This file tests the
tool that does the checking, and the properties that matter are not the
arithmetic — the engine has its own 62 tests — but these two:

* **An empty comparison must not pass.** The sentence this tool prints at the
  end lifts a watermark; it has to be covered by data.
* **A difference must name the input that explains it.** "These two numbers
  differ" is something a spreadsheet can say. Which rate to change is not.
"""

from __future__ import annotations

import pytest

from app.services.lohn import LohnKonfigurationFehlt
from app.services.lohn_vergleich import (
    VergleichsDateiFehler,
    bloecke,
    datum,
    vergleiche,
    wahrheit,
    zahl,
)

pytestmark = pytest.mark.asyncio

# Monatslohn 6'500, full month, no 13th, no Zulagen:
#   AHV 5.3 % = 344.50 · ALV 1.1 % = 71.50 · NBU 1.6 % = 104.00 · BVG 312.50
#   Abzüge 832.50 → Netto 5'667.50
#   AG: 344.50 + 71.50 + 52.00 (0.8 %) + 78.00 (1.2 %) + 9.75 (0.15 %) + 312.50 = 868.25
EINGABEN = """
[eingaben]
jahr: 2026
monat: 4
monatslohn: 6500.00
eintritt: 2020-01-01
geburtsdatum: 1986-05-04
dreizehnter: nein
brutto_ytd: 19500.00
ahv_satz_an: 5.3
alv_satz_an: 1.1
uvg_bu_satz: 0.8
uvg_nbu_satz: 1.6
fak_satz: 1.2
verwaltungskosten_satz: 0.15
bvg_an_monat: 312.50
bvg_ag_monat: 312.50
"""

STIMMT = (
    EINGABEN
    + """
[abrechnung]
brutto: 6500.00
ahv: 344.50
alv: 71.50
nbu: 104.00
bvg: 312.50
netto: 5667.50

[arbeitgeber]
ahv: 344.50
alv: 71.50
uvg_bu: 52.00
fak: 78.00
verwaltungskosten: 9.75
bvg: 312.50
total: 868.25
"""
)


def _mit(ersetze: dict[str, str], quelle: str = STIMMT) -> str:
    zeilen = []
    for zeile in quelle.splitlines():
        schluessel = zeile.split(":", 1)[0].strip().lower()
        zeilen.append(f"{schluessel}: {ersetze[schluessel]}" if schluessel in ersetze else zeile)
    return "\n".join(zeilen)


# --------------------------------------------------------------------------- #
# Lesen, so wie es auf dem Papier steht
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "erwartet"),
    [
        ("6'500.00", 6500.0),
        ("6’500.00", 6500.0),
        ("6 500.00", 6500.0),
        ("6500,00", 6500.0),
        ("6'500", 6500.0),
        ("CHF 6'500.00", 6500.0),
        ("  344.50  ", 344.50),
        ("-12.35", -12.35),
        ("", None),
        ("   ", None),
    ],
)
async def test_a_number_may_be_written_the_way_the_payslip_writes_it(text, erwartet):
    assert zahl(text) == erwartet


async def test_a_thousands_comma_is_not_a_decimal_comma():
    assert zahl("1,234.50") == 1234.50


async def test_what_is_not_a_number_says_so():
    with pytest.raises(VergleichsDateiFehler) as exc:
        zahl("ungefähr 6500")
    assert "6500" in str(exc.value)


@pytest.mark.parametrize("text", ["ja", "JA", "yes", "true", "1", "x"])
async def test_yes_in_the_forms_people_type(text):
    assert wahrheit(text) is True


@pytest.mark.parametrize("text", ["nein", "no", "false", "0", ""])
async def test_no_in_the_forms_people_type(text):
    assert wahrheit(text) is False


async def test_both_date_formats():
    assert datum("2026-04-30") == datum("30.04.2026")


async def test_a_line_before_the_first_block_is_refused():
    with pytest.raises(VergleichsDateiFehler) as exc:
        bloecke("monatslohn: 6500\n[eingaben]\n")
    assert "Block" in str(exc.value)


async def test_comments_and_blank_lines_are_ignored():
    gelesen = bloecke("# hallo\n\n[eingaben]\n  # noch einer\nmonatslohn: 6500  # dahinter\n")
    assert gelesen == {"eingaben": {"monatslohn": "6500"}}


async def test_a_typo_in_an_input_key_is_reported_not_ignored():
    """A silently ignored rate is exactly the bug this tool exists to find."""
    with pytest.raises(VergleichsDateiFehler) as exc:
        vergleiche(EINGABEN.replace("fak_satz:", "fka_satz:"))
    assert "fka_satz" in str(exc.value)


# --------------------------------------------------------------------------- #
# An empty comparison is not a passing comparison
# --------------------------------------------------------------------------- #


async def test_a_comparison_with_no_numbers_does_not_pass():
    """The sentence at the end lifts a watermark. It has to be covered."""
    ergebnis = vergleiche(EINGABEN + "\n[abrechnung]\n")

    assert ergebnis.stimmt is False
    assert any("Brutto" in b for b in ergebnis.befunde)


async def test_a_line_the_template_says_nothing_about_is_unchecked_not_matched():
    ohne_nbu = STIMMT.replace("nbu: 104.00\n", "")

    ergebnis = vergleiche(ohne_nbu)

    assert ergebnis.stimmt is False
    assert [z.name for z in ergebnis.ungeprueft] == ["NBU (Arbeitnehmer)"]
    assert any("Ungeprüft" in b and "NBU" in b for b in ergebnis.befunde)


async def test_a_line_the_template_omits_is_unchecked_not_zero():
    """ "They did not write it down" and "they wrote 0.00" are different claims,
    and only the second one is evidence."""
    text = STIMMT.replace("uvg_nbu_satz: 1.6\n", "uvg_nbu_satz: 1.6\nuvgz_satz_an: 0.5\n", 1)

    ergebnis = vergleiche(text)

    assert "UVGZ (Arbeitnehmer)" in [z.name for z in ergebnis.ungeprueft]
    assert not any("wirklich abgeschlossen" in b for b in ergebnis.befunde)


async def test_a_missing_netto_is_a_finding():
    ergebnis = vergleiche(STIMMT.replace("netto: 5667.50", "netto:"))

    assert ergebnis.stimmt is False
    assert any("Netto" in b for b in ergebnis.befunde)


async def test_a_full_match_passes_and_says_so():
    ergebnis = vergleiche(STIMMT)

    assert ergebnis.stimmt is True
    assert ergebnis.befunde == []
    assert ergebnis.abweichungen == []


# --------------------------------------------------------------------------- #
# A difference must name the input that explains it
# --------------------------------------------------------------------------- #


async def test_a_difference_names_the_input_that_controls_the_line():
    """Their NBU is 1.4 %, ours is 1.6 %."""
    ihre = 6500.00 * 1.4 / 100
    text = _mit({"nbu": f"{ihre:.2f}", "netto": f"{5667.50 + 104.00 - ihre:.2f}"})

    ergebnis = vergleiche(text)
    befund = next(b for b in ergebnis.befunde if b.startswith("NBU (Arbeitnehmer)"))

    assert "1.4 %" in befund
    assert "uvg_nbu_satz" in befund


async def test_a_difference_offers_both_readings_because_one_number_cannot_choose():
    """They applied 5.3 % to 6'800 — but the very same 360.40 is also 5.545 % of
    6'500. A tool that picked one would be confidently wrong half the time."""
    ihre = 6800.00 * 5.3 / 100
    text = _mit({"ahv": f"{ihre:.2f}", "netto": f"{5667.50 + 344.50 - ihre:.2f}"})

    ergebnis = vergleiche(text)
    befund = next(b for b in ergebnis.befunde if b.startswith("AHV/IV/EO (Arbeitnehmer)"))

    assert "anderer Satz" in befund
    assert "andere Basis" in befund
    assert "6800.00" in befund
    assert "ahv_satz_an" in befund


async def test_a_round_base_is_pointed_at_first():
    """6'800.00 is a number a human wrote down; 5.545 % is not."""
    text = _mit({"ahv": f"{6800.00 * 5.3 / 100:.2f}"})

    befund = next(b for b in vergleiche(text).befunde if b.startswith("AHV/IV/EO (Arbeitnehmer)"))

    assert "Die Basis 6800.00 ist eine runde Zahl" in befund


async def test_a_round_rate_is_pointed_at_first():
    """1.4 % is a number an insurer quotes; 5'687.50 is not."""
    text = _mit({"nbu": f"{6500.00 * 1.4 / 100:.2f}"})

    befund = next(b for b in vergleiche(text).befunde if b.startswith("NBU (Arbeitnehmer)"))

    assert "Der Satz 1.4 % ist eine runde Zahl" in befund


async def test_a_line_we_do_not_deduct_at_all_names_the_missing_input():
    # KTG is nowhere in the fixture, so it has to be added rather than replaced.
    text = STIMMT.replace("bvg: 312.50\n", "bvg: 312.50\nktg: 35.75\n", 1)

    ergebnis = vergleiche(text)
    befund = next(b for b in ergebnis.befunde if b.startswith("KTG (Arbeitnehmer)"))

    assert "ktg_satz_an" in befund
    assert "Fehlt" in befund


async def test_a_line_only_we_deduct_asks_whether_the_insurance_exists():
    """We charge UVGZ; their payslip shows 0.00 for it, which is a statement."""
    text = STIMMT.replace("uvg_nbu_satz: 1.6\n", "uvg_nbu_satz: 1.6\nuvgz_satz_an: 0.5\n", 1)
    text = text.replace("bvg: 312.50\nnetto:", "bvg: 312.50\nuvgz: 0.00\nnetto:", 1)

    ergebnis = vergleiche(text)

    assert any("UVGZ" in b and "wirklich abgeschlossen" in b for b in ergebnis.befunde)


async def test_a_few_rappen_are_called_rounding_not_a_wrong_rate():
    text = _mit({"ahv": "344.48", "netto": "5667.52"})

    ergebnis = vergleiche(text)
    befund = next(b for b in ergebnis.befunde if b.startswith("AHV/IV/EO (Arbeitnehmer)"))

    assert "Rappenrundung" in befund
    assert "Kein Eingabefehler" in befund


async def test_a_wrong_brutto_is_reported_first_and_alone():
    """Everything downstream follows from it; eight derived findings would bury
    the one cause."""
    text = _mit({"brutto": "6800.00"})

    ergebnis = vergleiche(text)

    assert len(ergebnis.befunde) == 1
    assert "Das Brutto stimmt nicht" in ergebnis.befunde[0]
    assert "Alles Weitere folgt daraus" in ergebnis.befunde[0]


async def test_a_line_only_the_template_has_is_reported_never_ignored():
    text = STIMMT + "sanierungsbeitrag: 45.00\n"

    ergebnis = vergleiche(text)

    assert ergebnis.stimmt is False
    assert any("sanierungsbeitrag" in b for b in ergebnis.befunde)


async def test_the_alv_ceiling_points_at_brutto_ytd():
    """Our ALV base is capped because the year-to-date gross says so; theirs is
    not. That is one input, and it is the one nobody thinks to check."""
    text = _mit({"brutto_ytd": "146000.00"}, STIMMT)
    text = _mit({"alv": "71.50"}, text)

    ergebnis = vergleiche(text)

    assert any("brutto_ytd" in b for b in ergebnis.befunde)


async def test_the_employer_side_is_compared_too():
    text = _mit({"fak": "84.50"})

    ergebnis = vergleiche(text)

    assert any(b.startswith("FAK (Arbeitgeber)") for b in ergebnis.befunde)
    assert ergebnis.stimmt is False


async def test_the_employer_block_may_be_left_out_entirely():
    """Not every old payslip shows it."""
    nur_an = STIMMT[: STIMMT.index("[arbeitgeber]")]

    ergebnis = vergleiche(nur_an)

    # Still not a pass — the employer lines are unchecked, and it says so.
    assert ergebnis.stimmt is False
    assert any("Ungeprüft" in b for b in ergebnis.befunde)


# --------------------------------------------------------------------------- #
# It refuses rather than guessing, like the engine it wraps
# --------------------------------------------------------------------------- #


async def test_a_missing_compulsory_rate_refuses_instead_of_estimating():
    ohne_fak = EINGABEN.replace("fak_satz: 1.2\n", "")

    with pytest.raises(LohnKonfigurationFehlt) as exc:
        vergleiche(ohne_fak + "\n[abrechnung]\nbrutto: 6500.00\n")

    assert any("FAK" in f for f in exc.value.fehlend)


async def test_a_missing_input_block_says_which_one():
    with pytest.raises(VergleichsDateiFehler) as exc:
        vergleiche("[abrechnung]\nbrutto: 6500.00\n")
    assert "eingaben" in str(exc.value)


async def test_a_missing_monatslohn_says_which_key():
    with pytest.raises(VergleichsDateiFehler) as exc:
        vergleiche("[eingaben]\njahr: 2026\nmonat: 4\n")
    assert "monatslohn" in str(exc.value)


# --------------------------------------------------------------------------- #
# Partial months and the 13th, because that is where payslips disagree
# --------------------------------------------------------------------------- #


async def test_a_mid_month_start_is_pro_rated_on_thirty_days():
    """The Swiss payroll month is 30 days whatever the calendar says."""
    text = _mit({"eintritt": "2026-04-16"}, EINGABEN) + "\n[abrechnung]\nbrutto: 3250.00\n"

    ergebnis = vergleiche(text)

    assert ergebnis.lauf.anteil == pytest.approx(0.5)
    assert ergebnis.lauf.brutto == 3250.00


async def test_the_thirteenth_shows_up_in_the_gross_line():
    text = _mit({"dreizehnter": "ja"}, EINGABEN) + "\n[abrechnung]\nbrutto: 13000.00\n"

    ergebnis = vergleiche(text)

    assert ergebnis.lauf.dreizehnter == 6500.00
    assert ergebnis.lauf.brutto == 13000.00


async def test_a_finding_names_the_side_it_is_on():
    """KTG, UVGZ and BVG exist on both sides and are *different* inputs. A
    finding that told you to fix `ktg_satz_an` for an employer-side difference
    would have you change the number and watch the difference stay."""
    text = STIMMT.replace("bvg: 312.50\nnetto:", "bvg: 312.50\nktg: 35.75\nnetto:", 1)
    text = text.replace("bvg: 312.50\ntotal:", "bvg: 312.50\nktg: 40.00\ntotal:", 1)

    befunde = vergleiche(text).befunde

    an = next(b for b in befunde if b.startswith("KTG (Arbeitnehmer)"))
    ag = next(b for b in befunde if b.startswith("KTG (Arbeitgeber)"))
    assert "ktg_satz_an" in an
    assert "ktg_satz_ag" in ag


async def test_a_line_cannot_be_built_without_a_side():
    """The default was `Arbeitnehmer`, and the one call that forgot to pass it
    silently mislabelled every employer line."""
    from app.services.lohn_vergleich import Zeile

    with pytest.raises(TypeError):
        Zeile("KTG", 1.0, 1.0, 0.5, 100.0)  # type: ignore[call-arg]
