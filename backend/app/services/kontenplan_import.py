"""Einen Kontenplan aus einer Datei lesen — und **zuerst zeigen, was passieren würde** (B-20).

Der letzte Schritt von B-20. Der Rest der Ersteinrichtung ist billig: ein
Musterbeleg, eine umsortierte Checkliste. Der Kontenplan ist es nicht — er ist
das Erste, was ein Treuhänder mitgibt, meist als Banana-Export oder als Liste
aus dem alten Programm, und ohne Import tippt man ihn ab.

Warum das ein Assistent ist und kein Knopf: ``PUT /api/kontenplan/`` **ersetzt
den ganzen Plan**. Wer eine Teilliste hochlädt und den Knopf drückt, verliert
den Rest — und merkt es erst beim nächsten Buchen. Deshalb ist das Lesen vom
Schreiben getrennt: der Vorschau-Schritt sagt pro Zeile, ob sie neu ist, etwas
ändert, nichts ändert oder nicht gelesen werden konnte, und der Schreibschritt
verlangt eine ausdrückliche Entscheidung zwischen *ergänzen* und *ersetzen*.

Was hier bewusst **nicht** passiert: raten. Eine Zeile ohne brauchbare
Kontonummer wird gemeldet, nicht repariert.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import pandas as pd

MAX_ZEILEN = 5_000

#: Spaltennamen, die in freier Wildbahn "Kontonummer" heissen. Banana schreibt
#: `Konto`/`Account`, Exporte aus anderen Programmen alles Mögliche.
SPALTEN_KONTO = (
    "konto",
    "kontonr",
    "konto nr",
    "konto nr.",
    "kontonummer",
    "kontonr.",
    "nummer",
    "nr",
    "nr.",
    "account",
    "accountnumber",
    "account number",
    "compte",
    "conto",
)

SPALTEN_BEZEICHNUNG = (
    "beschreibung",
    "bezeichnung",
    "kontobezeichnung",
    "text",
    "description",
    "libelle",
    "libellé",
    "descrizione",
    "name",
)

#: Banana-Kontennummern sind Ziffern; vierstellig im KMU-Kontenrahmen, aber
#: Unterkonten wie `1020.01` kommen vor. Alles andere (Gruppen-, Klassen- und
#: Summenzeilen wie `1`, `TOTAL`, `.`) ist keine Kontonummer.
KONTO_MUSTER = re.compile(r"^\d{3,6}(\.\d{1,4})?$")

NEU = "neu"
GEAENDERT = "geaendert"
UNVERAENDERT = "unveraendert"
UNGUELTIG = "ungueltig"

ERGAENZEN = "ergaenzen"
ERSETZEN = "ersetzen"
MODI = (ERGAENZEN, ERSETZEN)


class KontenplanDateiFehler(ValueError):
    """Die Datei lässt sich nicht als Kontenplan lesen."""


@dataclass(frozen=True)
class Zeile:
    konto: str
    bezeichnung: str
    status: str
    #: Nur bei `geaendert`: was heute im Mandanten steht.
    bisher: str = ""
    #: Nur bei `ungueltig`: warum.
    grund: str = ""
    #: Zeilennummer in der Datei, 1-basiert ohne Kopfzeile — damit der Nutzer
    #: die Zeile in seiner eigenen Datei wiederfindet.
    quelle: int = 0


@dataclass
class Vorschau:
    zeilen: list[Zeile] = field(default_factory=list)
    #: Konten, die der Mandant hat und die Datei nicht nennt. Bei `ersetzen`
    #: verschwinden sie — das ist der eine Satz, der vor dem Klick zählt.
    entfaellt: list[str] = field(default_factory=list)
    spalte_konto: str = ""
    spalte_bezeichnung: str = ""

    def zaehler(self) -> dict[str, int]:
        return {
            status: sum(1 for z in self.zeilen if z.status == status)
            for status in (NEU, GEAENDERT, UNVERAENDERT, UNGUELTIG)
        }

    def uebernehmbar(self) -> dict[str, str]:
        """Was ein Schreibschritt tatsächlich setzen würde."""
        return {z.konto: z.bezeichnung for z in self.zeilen if z.status in (NEU, GEAENDERT, UNVERAENDERT)}


def _tabelle(dateiname: str, inhalt: bytes) -> pd.DataFrame:
    name = (dateiname or "").lower()
    if name.endswith(".csv") or name.endswith(".txt"):
        try:
            return pd.read_csv(io.BytesIO(inhalt), sep=None, engine="python", dtype=str)
        except Exception as exc:  # pandas raises a zoo of them
            raise KontenplanDateiFehler(f"CSV konnte nicht gelesen werden: {exc}") from exc
    for engine in ("openpyxl", "xlrd"):
        try:
            return pd.read_excel(io.BytesIO(inhalt), engine=engine, dtype=str)
        except Exception:
            continue  # das andere Engine probieren
    raise KontenplanDateiFehler(
        "Unbekanntes Dateiformat. Erwartet wird eine CSV- oder Excel-Datei mit einer Spalte "
        "für die Kontonummer und einer für die Bezeichnung."
    )


def _spalte(spalten: list[str], kandidaten: tuple[str, ...]) -> str | None:
    normalisiert = {str(s).strip().lower(): s for s in spalten}
    for kandidat in kandidaten:
        if kandidat in normalisiert:
            return normalisiert[kandidat]
    return None


def _text(wert: object) -> str:
    if wert is None:
        return ""
    s = str(wert).strip()
    return "" if s.lower() in ("nan", "none", "nat") else s


def lesen(dateiname: str, inhalt: bytes, bestand: dict[str, str]) -> Vorschau:
    """Die Datei gegen den heutigen Kontenplan halten. Schreibt nichts."""
    df = _tabelle(dateiname, inhalt)
    if df.empty:
        raise KontenplanDateiFehler("Die Datei enthält keine Zeilen.")

    spalten = list(df.columns)
    konto_spalte = _spalte(spalten, SPALTEN_KONTO)
    bez_spalte = _spalte(spalten, SPALTEN_BEZEICHNUNG)
    if konto_spalte is None or bez_spalte is None:
        gefunden = ", ".join(str(s) for s in spalten[:15]) or "keine"
        raise KontenplanDateiFehler(
            f"Es braucht eine Spalte für die Kontonummer und eine für die Bezeichnung. Gefundene Spalten: {gefunden}."
        )

    if len(df) > MAX_ZEILEN:
        raise KontenplanDateiFehler(f"Die Datei hat {len(df)} Zeilen; höchstens {MAX_ZEILEN} werden gelesen.")

    vorschau = Vorschau(spalte_konto=str(konto_spalte), spalte_bezeichnung=str(bez_spalte))
    gesehen: dict[str, int] = {}

    for nummer, (_, row) in enumerate(df.iterrows(), start=1):
        konto = _text(row.get(konto_spalte))
        bezeichnung = _text(row.get(bez_spalte))

        if not konto and not bezeichnung:
            continue  # Leerzeile — kein Befund, das ist Formatierung.
        if not konto:
            # Banana-Gruppenzeilen ("Total Aktiven") haben eine Bezeichnung und
            # keine Kontonummer. Sie gehören nicht in den Kontenplan.
            continue
        if not KONTO_MUSTER.match(konto):
            vorschau.zeilen.append(Zeile(konto, bezeichnung, UNGUELTIG, grund="Keine Kontonummer.", quelle=nummer))
            continue
        if not bezeichnung:
            vorschau.zeilen.append(Zeile(konto, "", UNGUELTIG, grund="Bezeichnung fehlt.", quelle=nummer))
            continue

        if konto in gesehen:
            vorschau.zeilen.append(
                Zeile(
                    konto,
                    bezeichnung,
                    UNGUELTIG,
                    grund=f"Konto {konto} steht schon in Zeile {gesehen[konto]}.",
                    quelle=nummer,
                )
            )
            continue
        gesehen[konto] = nummer

        if konto not in bestand:
            status, bisher = NEU, ""
        elif bestand[konto] != bezeichnung:
            status, bisher = GEAENDERT, bestand[konto]
        else:
            status, bisher = UNVERAENDERT, bestand[konto]
        vorschau.zeilen.append(Zeile(konto, bezeichnung, status, bisher=bisher, quelle=nummer))

    if not vorschau.zeilen:
        raise KontenplanDateiFehler("In der Datei steht keine einzige Kontozeile.")

    vorschau.entfaellt = sorted(k for k in bestand if k not in gesehen)
    return vorschau


def anwenden(bestand: dict[str, str], vorschau: Vorschau, modus: str) -> dict[str, str]:
    """Der neue Kontenplan. Reine Funktion — der Aufrufer schreibt ihn."""
    if modus not in MODI:
        raise KontenplanDateiFehler(f"Unbekannter Modus: {modus}")
    if modus == ERSETZEN:
        return dict(vorschau.uebernehmbar())
    return {**bestand, **vorschau.uebernehmbar()}
