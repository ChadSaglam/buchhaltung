"""Das gesetzliche BVG-Minimum — als **Prüfung**, nicht als Berechnung (B-72, Option C).

Warum das hier steht und nicht in ``services/lohn.py``: die Altersgutschrift auf
der Lohnabrechnung kommt weiterhin von der Pensionskasse (``bvg_an_monat`` /
``bvg_ag_monat``). Das ist Absicht — ein echter Vorsorgeplan ist fast nie das
BVG-Obligatorium, und eine hier nachgerechnete Zahl würde der Abrechnung der
Kasse widersprechen, die bezahlt wird.

Was das Gesetz dagegen *schon* hergibt, ist eine **Untergrenze**. Sie ist
bundesrechtlich, nicht kantonal, und sie steht in einer Tabelle, die man
abtippen darf. Damit lässt sich beantworten, was sonst niemand von Hand prüft:

* Liegt die eingetragene Gutschrift **unter** dem Obligatorium? Dann stimmt
  entweder die Zahl nicht oder der Plan ist nicht gesetzeskonform.
* Zahlt der Arbeitgeber über die ganze Belegschaft **mindestens die Hälfte**?
  (Art. 66 Abs. 1 BVG vergleicht die Gesamtbeiträge des Arbeitgebers mit den
  Gesamtbeiträgen *aller* Arbeitnehmer — nicht Person für Person. Deshalb prüft
  diese Datei es auch nur über die Belegschaft, obwohl die Einzelprüfung
  verlockender aussähe.)

Nichts hier ändert eine Lohnabrechnung. Es sagt nur, wenn eine davon nicht
plausibel ist.

Quellen — nachgeschlagen, nicht erinnert:
* Grenzbeträge: BSV, «Wichtige Masszahlen im Bereich der beruflichen Vorsorge»
  (`BPP_Zahlen_85_2026.pdf`) und «Beträge gültig ab dem 1. Januar 2026».
* Altersgutschriftensätze: Art. 16 BVG, bestätigt in der BSV-Broschüre
  «Technische Aspekte der obligatorischen beruflichen Vorsorge».
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.models.mitarbeiter import Mitarbeiter
from app.services.export import round_chf


def _chf(value: float) -> float:
    """`round_chf` gibt Decimal zurück; hier wird durchgehend mit float gerechnet,
    wie im Lohnmodul (`services/lohn.py`)."""
    return float(round_chf(value))


@dataclass(frozen=True)
class BvgGrenzen:
    """Die vier Grenzbeträge eines Jahres, in Franken."""

    jahr: int
    eintrittsschwelle: float
    koordinationsabzug: float
    min_koordinierter_lohn: float
    obere_limite: float


#: Die Grenzbeträge werden per Verordnung angepasst, meist alle zwei Jahre.
#: **Neues Jahr = eine neue Zeile hier**, abgeschrieben von der BSV-Tabelle.
#: Nicht extrapolieren: 2005 hat sich die Eintrittsschwelle von einer Kopie des
#: Koordinationsabzugs zu einer eigenen Grösse entkoppelt, und wer zwischen zwei
#: Jahren interpoliert hätte, hätte das nicht kommen sehen.
GRENZBETRAEGE: dict[int, BvgGrenzen] = {
    2021: BvgGrenzen(2021, 21_510.0, 25_095.0, 3_585.0, 86_040.0),
    2022: BvgGrenzen(2022, 21_510.0, 25_095.0, 3_585.0, 86_040.0),
    2023: BvgGrenzen(2023, 22_050.0, 25_725.0, 3_675.0, 88_200.0),
    2024: BvgGrenzen(2024, 22_050.0, 25_725.0, 3_675.0, 88_200.0),
    2025: BvgGrenzen(2025, 22_680.0, 26_460.0, 3_780.0, 90_720.0),
    2026: BvgGrenzen(2026, 22_680.0, 26_460.0, 3_780.0, 90_720.0),
}

AELTESTES_JAHR = min(GRENZBETRAEGE)
JUENGSTES_JAHR = max(GRENZBETRAEGE)

#: Art. 16 BVG. Untergrenze des Altersjahrs → Ansatz in Prozent des
#: koordinierten Lohnes. Unter 25 wird nicht gespart (nur Risiko versichert),
#: darum beginnt die Tabelle dort und nicht bei 0.
ALTERSGUTSCHRIFTEN: tuple[tuple[int, float], ...] = (
    (25, 7.0),
    (35, 10.0),
    (45, 15.0),
    (55, 18.0),
)

SPARBEGINN_ALTER = ALTERSGUTSCHRIFTEN[0][0]


def grenzen_fuer(jahr: int) -> tuple[BvgGrenzen, bool]:
    """Die Grenzbeträge des Jahres, und ob sie tatsächlich für dieses Jahr gelten.

    Ein Jahr nach dem letzten hinterlegten wird gegen das letzte geprüft — eine
    Lohnbuchhaltung, die im Januar stehen bleibt, weil eine Tabelle veraltet
    ist, hilft niemandem. Das zweite Rückgabefeld ist ``False``, damit der
    Aufrufer genau das auf den Bildschirm schreiben kann, statt es zu verstecken.
    """
    if jahr in GRENZBETRAEGE:
        return GRENZBETRAEGE[jahr], True
    if jahr > JUENGSTES_JAHR:
        return GRENZBETRAEGE[JUENGSTES_JAHR], False
    return GRENZBETRAEGE[AELTESTES_JAHR], False


def altersjahr(geburtsdatum: date | None, jahr: int) -> int | None:
    """Das Altersjahr im Sinne von Art. 16 BVG: Kalenderjahr minus Geburtsjahr.

    Nicht das Alter am Stichtag — die Altersgutschrift wechselt zum Jahreswechsel
    das Band, nicht am Geburtstag.
    """
    return None if geburtsdatum is None else jahr - geburtsdatum.year


def altersgutschrift_satz(alter: int | None) -> float:
    """Ansatz in Prozent. Unter 25 (oder Alter unbekannt) wird nicht gespart."""
    if alter is None:
        return 0.0
    satz = 0.0
    for ab, prozent in ALTERSGUTSCHRIFTEN:
        if alter >= ab:
            satz = prozent
    return satz


def koordinierter_lohn(jahreslohn: float, grenzen: BvgGrenzen) -> float:
    """Der versicherte Lohn. 0, wenn die Eintrittsschwelle nicht erreicht ist."""
    if jahreslohn < grenzen.eintrittsschwelle:
        return 0.0
    roh = min(jahreslohn, grenzen.obere_limite) - grenzen.koordinationsabzug
    return _chf(max(roh, grenzen.min_koordinierter_lohn))


def mindest_altersgutschrift_jahr(jahreslohn: float, alter: int | None, grenzen: BvgGrenzen) -> float:
    """Was das Obligatorium für dieses Jahr mindestens verlangt — beide Teile zusammen."""
    koord = koordinierter_lohn(jahreslohn, grenzen)
    if not koord:
        return 0.0
    return _chf(koord * altersgutschrift_satz(alter) / 100.0)


@dataclass(frozen=True)
class BvgHinweis:
    """Ein Befund. ``mitarbeiter_id`` ist None, wenn er die Belegschaft betrifft."""

    code: str
    text: str
    mitarbeiter_id: int | None = None


def _jahreslohn(m: Mitarbeiter) -> float:
    monate = 13 if m.dreizehnter else 12
    return _chf((m.monatslohn or 0.0) * monate)


def pruefen(mitarbeiter: list[Mitarbeiter], jahr: int) -> list[BvgHinweis]:
    """Was an den eingetragenen BVG-Beträgen gegen das Obligatorium spricht.

    Reine Prüfung: ändert keine Abrechnung und verhindert keine. Was fehlt,
    statt falsch zu sein, meldet weiterhin ``lohn.fehlende_konfiguration`` und
    verweigert dort die Abrechnung.
    """
    grenzen, aktuell = grenzen_fuer(jahr)
    hinweise: list[BvgHinweis] = []

    if not aktuell:
        hinweise.append(
            BvgHinweis(
                "grenzbetraege_veraltet",
                f"Für {jahr} sind keine BVG-Grenzbeträge hinterlegt — geprüft wurde gegen {grenzen.jahr}.",
            )
        )

    summe_an = 0.0
    summe_ag = 0.0
    for m in mitarbeiter:
        an = m.bvg_an_monat or 0.0
        ag = m.bvg_ag_monat or 0.0
        summe_an += an
        summe_ag += ag

        jahreslohn = _jahreslohn(m)
        alter = altersjahr(m.geburtsdatum, jahr)
        minimum = mindest_altersgutschrift_jahr(jahreslohn, alter, grenzen)

        if m.geburtsdatum is None and jahreslohn >= grenzen.eintrittsschwelle:
            hinweise.append(
                BvgHinweis(
                    "geburtsdatum_fehlt",
                    f"{m.anzeige_name}: ohne Geburtsdatum lässt sich die gesetzliche "
                    "Mindest-Altersgutschrift nicht prüfen.",
                    m.id,
                )
            )
            continue

        if not minimum:
            continue

        tatsaechlich = _chf((an + ag) * 12)
        if tatsaechlich + 0.005 < minimum:
            hinweise.append(
                BvgHinweis(
                    "unter_obligatorium",
                    f"{m.anzeige_name}: {tatsaechlich:.2f} CHF Altersgutschrift im Jahr, "
                    f"das Obligatorium verlangt {minimum:.2f} CHF "
                    f"({altersgutschrift_satz(alter):.0f} % von {koordinierter_lohn(jahreslohn, grenzen):.2f} CHF "
                    f"koordiniertem Lohn, Altersjahr {alter}).",
                    m.id,
                )
            )

    # Art. 66 Abs. 1 BVG vergleicht die Summen, nicht die einzelnen Personen.
    if summe_an and _chf(summe_ag) + 0.005 < _chf(summe_an):
        hinweise.append(
            BvgHinweis(
                "arbeitgeber_unter_haelfte",
                f"Der Arbeitgeberanteil ({_chf(summe_ag):.2f} CHF im Monat) ist kleiner als der "
                f"Arbeitnehmeranteil ({_chf(summe_an):.2f} CHF). Art. 66 Abs. 1 BVG verlangt über die "
                "ganze Belegschaft mindestens gleich hohe Arbeitgeberbeiträge.",
            )
        )

    return hinweise
