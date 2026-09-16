"""Unsere Lohnabrechnung gegen die des bisherigen Anbieters halten (B-72).

Das Wasserzeichen auf jeder Lohnabrechnung — «Nicht für die Einreichung» —
verschwindet erst, wenn **ein echter Monat** gegen den bisherigen Anbieter
geprüft wurde. Diese Datei ist das Werkzeug dafür, und sie ist nur deshalb
Code und nicht eine Tabelle: eine Differenz von 4 Rappen und eine Differenz,
die aus einem falschen Satz kommt, sehen in einer Tabelle gleich aus.

**Sie passt nichts an.** Sie rechnet mit unserer Engine, stellt das Ergebnis
neben die Vorlage und sagt, *welche Eingabe* die Differenz erklären würde. Ein
Vergleich, der unsere Zahl an die fremde anpasst, hätte den Zweck verfehlt,
bevor er gelaufen ist.

Eingabe ist eine Textdatei mit drei Blöcken (siehe ``docs/LOHN-VERGLEICH.md``):

``[eingaben]``      was der Arbeitgeber weiss — Lohn, Sätze, BVG-Beträge
``[abrechnung]``    was auf der alten Abrechnung steht (Arbeitnehmerseite)
``[arbeitgeber]``   dasselbe für die Arbeitgeberseite, optional

Zahlen dürfen so abgeschrieben werden, wie sie auf dem Papier stehen:
``6'500.00``, ``6 500,00``, ``6500`` sind dieselbe Zahl.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.models.lohn_settings import LohnSettings
from app.models.mitarbeiter import Mitarbeiter
from app.services.export import round_chf
from app.services.lohn import Abzug, Lohnlauf, berechnen

#: Ab welcher Differenz es keine Rundung mehr ist. Fünf Rappen: eine Zeile, die
#: zeilenweise statt auf dem Total gerundet wird, weicht um höchstens einen
#: halben Rappen pro Zeile ab, und mehr als ein paar Zeilen hat keine Abrechnung.
RUNDUNG_GRENZE = 0.05

#: Wie eng ein Satz getroffen sein muss, um "derselbe Satz" zu heissen.
SATZ_GRENZE = 0.005


class VergleichsDateiFehler(ValueError):
    """Die Datei lässt sich nicht als Vergleich lesen."""


# --------------------------------------------------------------------------- #
# Lesen
# --------------------------------------------------------------------------- #

_WAHR = {"ja", "yes", "true", "1", "x"}
_FALSCH = {"nein", "no", "false", "0", ""}


def zahl(text: str | None) -> float | None:
    """``6'500.00`` · ``6 500,00`` · ``6500`` → 6500.0. Leer → None."""
    if text is None:
        return None
    roh = text.strip()
    if not roh:
        return None
    for mark in ("'", "’", "´", " ", " ", " ", "CHF", "chf"):
        roh = roh.replace(mark, "")
    # Ein einzelnes Komma ohne Punkt ist ein Dezimaltrennzeichen (1234,50);
    # sonst ist es ein Tausendertrennzeichen und fällt weg.
    dezimalkomma = roh.count(",") == 1 and roh.count(".") == 0
    roh = roh.replace(",", "." if dezimalkomma else "")
    try:
        return float(roh)
    except ValueError as exc:
        raise VergleichsDateiFehler(f"«{text.strip()}» ist keine Zahl.") from exc


def wahrheit(text: str | None) -> bool:
    roh = (text or "").strip().lower()
    if roh in _WAHR:
        return True
    if roh in _FALSCH:
        return False
    raise VergleichsDateiFehler(f"«{text}» ist kein ja/nein.")


def datum(text: str | None) -> date | None:
    roh = (text or "").strip()
    if not roh:
        return None
    for muster, reihenfolge in ((r"^(\d{4})-(\d{2})-(\d{2})$", (1, 2, 3)), (r"^(\d{2})\.(\d{2})\.(\d{4})$", (3, 2, 1))):
        treffer = re.match(muster, roh)
        if treffer:
            jahr, monat, tag = (int(treffer.group(i)) for i in reihenfolge)
            return date(jahr, monat, tag)
    raise VergleichsDateiFehler(f"«{roh}» ist kein Datum (JJJJ-MM-TT oder TT.MM.JJJJ).")


def bloecke(inhalt: str) -> dict[str, dict[str, str]]:
    """``[block]`` + ``schlüssel: wert``. ``#`` ist ein Kommentar."""
    gelesen: dict[str, dict[str, str]] = {}
    aktuell: str | None = None
    for nummer, zeile in enumerate(inhalt.splitlines(), start=1):
        roh = zeile.split("#", 1)[0].strip()
        if not roh:
            continue
        if roh.startswith("[") and roh.endswith("]"):
            aktuell = roh[1:-1].strip().lower()
            gelesen.setdefault(aktuell, {})
            continue
        if aktuell is None:
            raise VergleichsDateiFehler(f"Zeile {nummer}: «{roh}» steht vor dem ersten [Block].")
        trenner = ":" if ":" in roh else ("=" if "=" in roh else "")
        if not trenner:
            raise VergleichsDateiFehler(f"Zeile {nummer}: «{roh}» ist kein «schlüssel: wert».")
        schluessel, _, wert = roh.partition(trenner)
        gelesen[aktuell][schluessel.strip().lower()] = wert.strip()
    return gelesen


# --------------------------------------------------------------------------- #
# Die Eingaben zu Engine-Objekten machen
# --------------------------------------------------------------------------- #

#: Was ``[eingaben]`` kennt. Alles andere dort ist ein Tippfehler und wird
#: gemeldet — ein stillschweigend ignorierter Satz ist genau der Fehler, den
#: dieser Vergleich finden soll.
EINGABE_FELDER: tuple[str, ...] = (
    "jahr",
    "monat",
    "monatslohn",
    "pensum",
    "eintritt",
    "austritt",
    "geburtsdatum",
    "dreizehnter",
    "zulagen",
    "brutto_ytd",
    "kinder",
    "kanton",
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
    "bvg_an_monat",
    "bvg_ag_monat",
    "quellensteuer",
    "quellensteuer_satz",
)

#: Zeilenname der Engine → Schlüssel in ``[abrechnung]``.
AN_ZEILEN: dict[str, str] = {
    "AHV/IV/EO": "ahv",
    "ALV": "alv",
    "NBU": "nbu",
    "UVGZ": "uvgz",
    "KTG": "ktg",
    "BVG": "bvg",
    "Quellensteuer": "quellensteuer",
}

#: Dasselbe für ``[arbeitgeber]``. AHV und ALV heissen dort gleich, UVG BU nicht.
AG_ZEILEN: dict[str, str] = {
    "AHV/IV/EO": "ahv",
    "ALV": "alv",
    "UVG BU": "uvg_bu",
    "UVGZ": "uvgz",
    "KTG": "ktg",
    "FAK": "fak",
    "Verwaltungskosten": "verwaltungskosten",
    "BVG": "bvg",
}

AN = "Arbeitnehmer"
AG = "Arbeitgeber"

#: Welche Eingabe eine Zeile steuert — für die Diagnose. **Pro Seite**, weil
#: KTG, UVGZ und BVG auf beiden Seiten vorkommen und dort verschiedene Felder
#: sind: einen Befund, der auf der Arbeitgeberseite `ktg_satz_an` nennt, würde
#: man korrigieren und die Differenz bliebe stehen.
ZEILE_ZU_EINGABE: dict[tuple[str, str], str] = {
    (AN, "AHV/IV/EO"): "ahv_satz_an",
    (AN, "ALV"): "alv_satz_an",
    (AN, "NBU"): "uvg_nbu_satz",
    (AN, "UVGZ"): "uvgz_satz_an",
    (AN, "KTG"): "ktg_satz_an",
    (AN, "BVG"): "bvg_an_monat",
    (AN, "Quellensteuer"): "quellensteuer_satz",
    (AG, "AHV/IV/EO"): "ahv_satz_an",
    (AG, "ALV"): "alv_satz_an",
    (AG, "UVG BU"): "uvg_bu_satz",
    (AG, "UVGZ"): "uvgz_satz_ag",
    (AG, "KTG"): "ktg_satz_ag",
    (AG, "FAK"): "fak_satz",
    (AG, "Verwaltungskosten"): "verwaltungskosten_satz",
    (AG, "BVG"): "bvg_ag_monat",
}


def _pflicht(werte: dict[str, str], schluessel: str) -> str:
    if schluessel not in werte or not werte[schluessel].strip():
        raise VergleichsDateiFehler(f"[eingaben] braucht «{schluessel}».")
    return werte[schluessel]


def objekte(eingaben: dict[str, str]) -> tuple[Mitarbeiter, LohnSettings, int, int, float, bool, float]:
    """Aus dem Eingabeblock die Engine-Argumente bauen. Keine Datenbank."""
    unbekannt = sorted(set(eingaben) - set(EINGABE_FELDER))
    if unbekannt:
        raise VergleichsDateiFehler(f"[eingaben] kennt diese Schlüssel nicht: {', '.join(unbekannt)}")

    person = Mitarbeiter(
        id=0,
        vorname="Vergleich",
        name="Testfall",
        monatslohn=zahl(_pflicht(eingaben, "monatslohn")) or 0.0,
        pensum=zahl(eingaben.get("pensum")) or 100.0,
        eintritt=datum(eingaben.get("eintritt")),
        austritt=datum(eingaben.get("austritt")),
        geburtsdatum=datum(eingaben.get("geburtsdatum")),
        dreizehnter=wahrheit(eingaben.get("dreizehnter", "nein")),
        kinder=int(zahl(eingaben.get("kinder")) or 0),
        kanton=(eingaben.get("kanton") or "")[:2].upper(),
        bvg_an_monat=zahl(eingaben.get("bvg_an_monat")),
        bvg_ag_monat=zahl(eingaben.get("bvg_ag_monat")),
        quellensteuer=wahrheit(eingaben.get("quellensteuer", "nein")),
        quellensteuer_satz=zahl(eingaben.get("quellensteuer_satz")),
    )
    settings = LohnSettings(
        id=0,
        tenant_id=0,
        ahv_satz_an=zahl(eingaben.get("ahv_satz_an")) or 5.3,
        alv_satz_an=zahl(eingaben.get("alv_satz_an")) or 1.1,
        alv_jahresgrenze=zahl(eingaben.get("alv_jahresgrenze")) or 148_200.0,
        uvg_bu_satz=zahl(eingaben.get("uvg_bu_satz")),
        uvg_nbu_satz=zahl(eingaben.get("uvg_nbu_satz")),
        uvgz_satz_an=zahl(eingaben.get("uvgz_satz_an")),
        uvgz_satz_ag=zahl(eingaben.get("uvgz_satz_ag")),
        ktg_satz_an=zahl(eingaben.get("ktg_satz_an")),
        ktg_satz_ag=zahl(eingaben.get("ktg_satz_ag")),
        fak_satz=zahl(eingaben.get("fak_satz")),
        verwaltungskosten_satz=zahl(eingaben.get("verwaltungskosten_satz")),
    )
    return (
        person,
        settings,
        int(zahl(_pflicht(eingaben, "jahr")) or 0),
        int(zahl(_pflicht(eingaben, "monat")) or 0),
        zahl(eingaben.get("zulagen")) or 0.0,
        wahrheit(eingaben.get("dreizehnter", "nein")),
        zahl(eingaben.get("brutto_ytd")) or 0.0,
    )


# --------------------------------------------------------------------------- #
# Vergleichen
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Zeile:
    """Eine Zeile, zweimal gerechnet."""

    label: str
    unser: float
    vorlage: float | None
    satz: float
    basis: float
    #: Ohne Default: eine Zeile, die nicht weiss, auf welcher Seite sie steht,
    #: nennt in der Diagnose das falsche Eingabefeld — KTG, UVGZ und BVG gibt es
    #: auf beiden Seiten und es sind verschiedene Felder.
    seite: str

    @property
    def name(self) -> str:
        return f"{self.label} ({self.seite})"

    @property
    def differenz(self) -> float:
        return 0.0 if self.vorlage is None else float(round_chf(self.unser - self.vorlage))

    @property
    def stimmt(self) -> bool:
        return self.vorlage is None or abs(self.differenz) < 0.005

    @property
    def nur_rundung(self) -> bool:
        return not self.stimmt and abs(self.differenz) <= RUNDUNG_GRENZE


@dataclass
class Vergleich:
    lauf: Lohnlauf
    brutto_vorlage: float | None = None
    netto_vorlage: float | None = None
    ag_total_vorlage: float | None = None
    an_zeilen: list[Zeile] = field(default_factory=list)
    ag_zeilen: list[Zeile] = field(default_factory=list)
    unbekannte_zeilen: list[str] = field(default_factory=list)
    befunde: list[str] = field(default_factory=list)

    @property
    def abweichungen(self) -> list[Zeile]:
        return [z for z in self.an_zeilen + self.ag_zeilen if not z.stimmt]

    @property
    def ungeprueft(self) -> list[Zeile]:
        """Zeilen, die wir rechnen und zu denen die Vorlage nichts sagt."""
        return [z for z in self.an_zeilen + self.ag_zeilen if z.vorlage is None]

    @property
    def stimmt(self) -> bool:
        """Nur wahr, wenn tatsächlich verglichen wurde.

        Eine leere Vergleichsdatei darf **nicht** "stimmt" sagen. Der Satz, den
        dieses Werkzeug am Ende ausspricht, hebt ein Wasserzeichen auf; er muss
        gedeckt sein. Also: Brutto und Netto genannt, jede Zeile, die wir
        rechnen, hat ein Gegenstück, und keine davon weicht ab.
        """
        if self.brutto_vorlage is None or self.netto_vorlage is None:
            return False
        if self.ungeprueft:
            return False
        return not self.abweichungen and not self.unbekannte_zeilen and not self._totale_weichen_ab()

    def _totale_weichen_ab(self) -> bool:
        paare = (
            (self.lauf.brutto, self.brutto_vorlage),
            (self.lauf.netto, self.netto_vorlage),
            (self.lauf.ag_total, self.ag_total_vorlage),
        )
        return any(v is not None and abs(float(round_chf(u - v))) >= 0.005 for u, v in paare)


def _zeilen(
    unsere: list[Abzug], vorlage: dict[str, str], namen: dict[str, str], seite: str
) -> tuple[list[Zeile], list[str]]:
    gesehen: set[str] = set()
    zeilen: list[Zeile] = []
    for abzug in unsere:
        schluessel = namen.get(abzug.label)
        if schluessel is None:
            continue
        gesehen.add(schluessel)
        zeilen.append(Zeile(abzug.label, abzug.betrag, zahl(vorlage.get(schluessel)), abzug.satz, abzug.basis, seite))
    # Zeilen, die nur die Vorlage kennt: wir ziehen sie gar nicht ab.
    for label, schluessel in namen.items():
        if schluessel in gesehen:
            continue
        betrag = zahl(vorlage.get(schluessel))
        if betrag:
            zeilen.append(Zeile(label, 0.0, betrag, 0.0, 0.0, seite))
    return zeilen, sorted(
        s for s in vorlage if s not in set(namen.values()) and s not in {"brutto", "netto", "abzuege_total", "total"}
    )


def _glatter_satz(wert: float) -> bool:
    """Ein Satz, wie ihn eine Versicherung offeriert: höchstens zwei Nachkommastellen."""
    return abs(wert * 100 - round(wert * 100)) < 1e-6


def _glatte_basis(wert: float) -> bool:
    """Ein Betrag, den jemand von Hand gesetzt hat. Jeder Franken hat zwei
    Nachkommastellen, das sagt also nichts — ein Vielfaches von 50 schon."""
    return abs(wert / 50.0 - round(wert / 50.0)) < 1e-9


def _satz_der_vorlage(zeile: Zeile) -> float | None:
    if not zeile.basis or zeile.vorlage is None:
        return None
    return round(zeile.vorlage / zeile.basis * 100.0, 4)


def diagnose(vergleich: Vergleich) -> list[str]:
    """Für jede Abweichung: welche Eingabe sie erklären würde."""
    befunde: list[str] = []
    lauf = vergleich.lauf

    # Zuerst das Brutto. Weicht es ab, folgt alles Weitere daraus, und eine Liste
    # von acht abgeleiteten Differenzen verdeckt die eine Ursache.
    if vergleich.brutto_vorlage is not None and abs(float(round_chf(lauf.brutto - vergleich.brutto_vorlage))) >= 0.005:
        befunde.append(
            f"**Das Brutto stimmt nicht**: wir {lauf.brutto:.2f}, Vorlage {vergleich.brutto_vorlage:.2f} "
            f"(Differenz {lauf.brutto - vergleich.brutto_vorlage:+.2f}). Grundlohn {lauf.grundlohn:.2f} · "
            f"13. {lauf.dreizehnter:.2f} · Zulagen {lauf.zulagen:.2f}, Monatsanteil {lauf.anteil:.4f}. "
            "Alles Weitere folgt daraus — zuerst das hier klären."
        )
        return befunde

    for zeile in vergleich.an_zeilen + vergleich.ag_zeilen:
        if zeile.stimmt:
            continue
        eingabe = ZEILE_ZU_EINGABE.get((zeile.seite, zeile.label), "—")

        if zeile.nur_rundung:
            befunde.append(
                f"{zeile.name}: {zeile.differenz:+.2f} — Rappenrundung. Die Vorlage rundet vermutlich "
                "auf dem Total statt je Zeile. Kein Eingabefehler."
            )
            continue
        if zeile.unser == 0.0:
            befunde.append(
                f"{zeile.name}: wir ziehen nichts ab, die Vorlage {zeile.vorlage:.2f}. "
                f"Fehlt «{eingabe}» in [eingaben]? Ohne Satz rechnen wir die Zeile nicht."
            )
            continue
        if not zeile.vorlage:
            befunde.append(
                f"{zeile.name}: wir ziehen {zeile.unser:.2f} ab, die Vorlage kennt die Zeile nicht. "
                f"Ist diese Versicherung wirklich abgeschlossen? Sonst «{eingabe}» leeren."
            )
            continue

        if zeile.satz:
            # Eine einzelne Zahl sagt **nicht**, ob der Satz oder die Basis anders
            # ist: jede Differenz lässt sich als beides lesen. Also werden beide
            # Lesarten hingeschrieben, statt eine davon zu behaupten — eine
            # geratene Ursache ist genau die Sorte plausibler falscher Antwort,
            # die dieses Werkzeug finden soll.
            vorlage_satz = _satz_der_vorlage(zeile) or 0.0
            basis_vorlage = zeile.vorlage / zeile.satz * 100.0
            hinweis = ""
            if _glatter_satz(vorlage_satz) and not _glatte_basis(basis_vorlage):
                hinweis = f" Der Satz {vorlage_satz:.4g} % ist eine runde Zahl — dort zuerst nachsehen."
            elif _glatte_basis(basis_vorlage) and not _glatter_satz(vorlage_satz):
                hinweis = f" Die Basis {basis_vorlage:.2f} ist eine runde Zahl — dort zuerst nachsehen."
            befunde.append(
                f"{zeile.name}: {zeile.differenz:+.2f}. Zwei Lesarten, und eine Zahl kann sie nicht trennen — "
                f"**anderer Satz**: die Vorlage rechnet mit {vorlage_satz:.4g} % statt {zeile.satz:.4g} % "
                f"(«{eingabe}»); oder **andere Basis**: sie rechnet auf {basis_vorlage:.2f} statt "
                f"{zeile.basis:.2f} (Zulagen, 13. Monatslohn, Monatsanteil).{hinweis}"
            )
            continue
        befunde.append(
            f"{zeile.name}: wir {zeile.unser:.2f}, Vorlage {zeile.vorlage:.2f} ({zeile.differenz:+.2f}). "
            f"Das ist ein Betrag, kein Satz — «{eingabe}» gegen die Abrechnung der Kasse prüfen."
        )

    # Die ALV-Grenze ist die einzige Zeile mit einem Gedächtnis.
    alv = next((z for z in vergleich.an_zeilen if z.label == "ALV"), None)
    if alv is not None and not alv.stimmt and not alv.nur_rundung and alv.basis < lauf.brutto:
        befunde.append(
            f"ALV: unsere Basis ({alv.basis:.2f}) ist kleiner als das Brutto ({lauf.brutto:.2f}) — die "
            "Jahresgrenze greift schon. Stimmt «brutto_ytd»? Das ist der im Jahr bereits bezahlte Bruttolohn "
            "**vor** diesem Monat."
        )

    # Fehlende Gegenstücke sind kein Treffer, sondern eine Lücke. Ein Vergleich,
    # der über eine ungeprüfte Zeile hinwegliest, ist der Grund, warum dieses
    # Werkzeug überhaupt existiert.
    if vergleich.brutto_vorlage is None:
        befunde.append("Die Vorlage nennt kein Brutto. Ohne das ist nichts vergleichbar.")
    if vergleich.netto_vorlage is None:
        befunde.append("Die Vorlage nennt kein Netto — das ist die Zahl, die der Mitarbeiter sieht.")
    ungeprueft = [z.name for z in vergleich.ungeprueft]
    if ungeprueft:
        befunde.append(
            "Ungeprüft, weil die Vorlage dazu nichts sagt: "
            + ", ".join(ungeprueft)
            + ". Nachtragen oder — wenn die alte Abrechnung die Zeile wirklich nicht hat — als Befund behandeln."
        )

    for schluessel in vergleich.unbekannte_zeilen:
        befunde.append(
            f"Die Vorlage hat eine Zeile «{schluessel}», die wir nicht kennen. Eine Abrechnung mit einer Zeile, "
            "die unsere Engine nicht abbildet, ist noch nicht vergleichbar — nicht überschreiben, melden."
        )

    if vergleich.netto_vorlage is not None:
        delta = float(round_chf(lauf.netto - vergleich.netto_vorlage))
        if abs(delta) >= 0.005 and not vergleich.abweichungen:
            befunde.append(
                f"Jede Zeile stimmt, das Netto nicht ({delta:+.2f}). Dann rundet die Vorlage das Total anders "
                "als die Summe ihrer Zeilen."
            )
    return befunde


def vergleiche(inhalt: str) -> Vergleich:
    """Die Vergleichsdatei lesen, unsere Abrechnung rechnen, beide nebeneinander legen."""
    gelesen = bloecke(inhalt)
    if "eingaben" not in gelesen:
        raise VergleichsDateiFehler("Der Block [eingaben] fehlt.")
    person, settings, jahr, monat, zulagen, dreizehnter, brutto_ytd = objekte(gelesen["eingaben"])

    lauf = berechnen(
        mitarbeiter=person,
        settings=settings,
        jahr=jahr,
        monat=monat,
        zulagen=zulagen,
        dreizehnter=dreizehnter,
        brutto_ytd=brutto_ytd,
    )

    abrechnung = gelesen.get("abrechnung", {})
    arbeitgeber = gelesen.get("arbeitgeber", {})
    an_zeilen, an_unbekannt = _zeilen(lauf.abzuege, abrechnung, AN_ZEILEN, AN)
    ag_zeilen, ag_unbekannt = _zeilen(lauf.arbeitgeber, arbeitgeber, AG_ZEILEN, AG)

    vergleich = Vergleich(
        lauf=lauf,
        brutto_vorlage=zahl(abrechnung.get("brutto")),
        netto_vorlage=zahl(abrechnung.get("netto")),
        ag_total_vorlage=zahl(arbeitgeber.get("total")),
        an_zeilen=an_zeilen,
        ag_zeilen=ag_zeilen,
        unbekannte_zeilen=sorted(set(an_unbekannt) | set(ag_unbekannt)),
    )
    vergleich.befunde = diagnose(vergleich)
    return vergleich
