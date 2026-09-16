#!/usr/bin/env python3
"""Unsere Lohnabrechnung gegen die des bisherigen Anbieters (B-72).

    python scripts/lohn-vergleich.py meine-abrechnung.txt

Die Vorlage für die Eingabedatei steht in ``docs/LOHN-VERGLEICH.md``; mit
``--vorlage`` schreibt dieses Skript sie auf die Standardausgabe.

Exit-Code 0, wenn alles auf den Rappen stimmt, sonst 1 — damit der Vergleich
auch in einer Checkliste stehen kann und nicht nur auf einem Bildschirm.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Der Backend-Code lebt im venv (`make setup`). Wer `python3 scripts/…` tippt —
# und das tut jeder — landet sonst bei einem ModuleNotFoundError für sqlalchemy,
# was nach einem kaputten Skript aussieht und keins ist. Also: einmal selbst ins
# venv wechseln, still, und nur wenn es eines gibt.


def _im_venv_neu_starten() -> None:
    """Einmal ins venv wechseln, still, und nur wenn es eines gibt.

    Der Backend-Code lebt im venv (`make setup`). Wer `python3 scripts/...`
    tippt - und das tut jeder - landet sonst bei einem ModuleNotFoundError fuer
    sqlalchemy, was nach einem kaputten Skript aussieht und keins ist.
    """
    try:
        import sqlalchemy  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        return
    venv_python = ROOT / "backend" / "venv" / "bin" / "python"
    schon_drin = venv_python.exists() and Path(sys.executable).resolve() == venv_python.resolve()
    if not venv_python.exists() or schon_drin:
        print(
            "Dieses Skript braucht die Backend-Abhaengigkeiten. Einmal `make setup`, oder direkt: "
            "backend/venv/bin/python scripts/lohn-vergleich.py <datei>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


_im_venv_neu_starten()

from app.services.lohn import LohnKonfigurationFehlt  # noqa: E402
from app.services.lohn_vergleich import (  # noqa: E402
    Vergleich,
    VergleichsDateiFehler,
    Zeile,
    vergleiche,
)

VORLAGE = """# Ein Monat, zweimal gerechnet. Zahlen dürfen so abgeschrieben werden,
# wie sie auf dem Papier stehen: 6'500.00, 6 500,00 und 6500 sind dasselbe.

[eingaben]
# Was der Arbeitgeber weiss — unsere Engine rechnet daraus.
jahr: 2026
monat: 4
monatslohn: 6500.00
pensum: 100
eintritt: 2020-01-01
austritt:
geburtsdatum: 1986-05-04
dreizehnter: nein
zulagen: 0.00
# Bruttolohn, der diesem Mitarbeiter dieses Jahr VOR diesem Monat bezahlt wurde.
# Das ist es, was die ALV-Jahresgrenze kumulativ macht.
brutto_ytd: 19500.00

ahv_satz_an: 5.3
alv_satz_an: 1.1
alv_jahresgrenze: 148200
uvg_bu_satz: 0.8
uvg_nbu_satz: 1.6
uvgz_satz_an:
uvgz_satz_ag:
ktg_satz_an:
ktg_satz_ag:
fak_satz: 1.2
verwaltungskosten_satz: 0.15
# Beträge aus der Abrechnung der Pensionskasse, pro Monat.
bvg_an_monat: 312.50
bvg_ag_monat: 312.50
quellensteuer: nein
quellensteuer_satz:

[abrechnung]
# Was auf der alten Abrechnung steht — Arbeitnehmerseite.
brutto: 6500.00
ahv:
alv:
nbu:
uvgz:
ktg:
bvg:
quellensteuer:
netto:

[arbeitgeber]
# Optional. Weglassen, wenn die alte Abrechnung die Arbeitgeberseite nicht zeigt.
ahv:
alv:
uvg_bu:
uvgz:
ktg:
fak:
verwaltungskosten:
bvg:
total:
"""


def _zeile(z: Zeile) -> str:
    vorlage = f"{'—':>10}" if z.vorlage is None else f"{z.vorlage:>10.2f}"
    differenz = f"{'':>10}" if z.vorlage is None else f"{z.differenz:>+10.2f}"
    herkunft = f"{z.basis:.2f} × {z.satz:.4g} %" if z.satz else ("Betrag der Kasse" if z.unser else "")
    marke = " " if z.stimmt else ("~" if z.nur_rundung else "!")
    return f" {marke} {z.label:<18}{z.unser:>10.2f}{vorlage}{differenz}   {herkunft}".rstrip()


def bericht(v: Vergleich) -> str:
    lauf = v.lauf
    zeilen = [
        f"Periode {lauf.periode} · Monatsanteil {lauf.anteil:.4f}",
        "",
        f"{'':4}{'Zeile':<18}{'wir':>10}{'Vorlage':>10}{'Differenz':>10}   Basis × Satz",
        "-" * 78,
        f"    {'Brutto':<18}{lauf.brutto:>10.2f}"
        + (f"{'—':>10}" if v.brutto_vorlage is None else f"{v.brutto_vorlage:>10.2f}")
        + ("" if v.brutto_vorlage is None else f"{lauf.brutto - v.brutto_vorlage:>+10.2f}"),
        "",
        "  Arbeitnehmer",
    ]
    zeilen += [_zeile(z) for z in v.an_zeilen]
    zeilen += [
        "-" * 78,
        f"    {'Netto':<18}{lauf.netto:>10.2f}"
        + (f"{'—':>10}" if v.netto_vorlage is None else f"{v.netto_vorlage:>10.2f}")
        + ("" if v.netto_vorlage is None else f"{lauf.netto - v.netto_vorlage:>+10.2f}"),
    ]
    if v.ag_zeilen:
        zeilen += ["", "  Arbeitgeber"]
        zeilen += [_zeile(z) for z in v.ag_zeilen]
        zeilen += [
            "-" * 78,
            f"    {'Total Arbeitgeber':<18}{lauf.ag_total:>10.2f}"
            + (f"{'—':>10}" if v.ag_total_vorlage is None else f"{v.ag_total_vorlage:>10.2f}")
            + ("" if v.ag_total_vorlage is None else f"{lauf.ag_total - v.ag_total_vorlage:>+10.2f}"),
        ]

    zeilen += ["", ""]
    if v.stimmt:
        zeilen += [
            "✓ Stimmt auf den Rappen.",
            "",
            "  Das ist die Bedingung aus B-72: erst wenn ein echter Monat übereinstimmt,",
            "  darf die Freigabe in *Lohn* gesetzt werden und das Wasserzeichen",
            "  «Nicht für die Einreichung» verschwindet.",
        ]
    else:
        zeilen += [f"✗ {len(v.befunde)} Befund(e):", ""]
        zeilen += [f"  {i}. {text}" for i, text in enumerate(v.befunde, start=1)]
    return "\n".join(zeilen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lohn-vergleich", description=__doc__.split("\n\n")[0])
    parser.add_argument("datei", nargs="?", help="Vergleichsdatei (siehe --vorlage)")
    parser.add_argument("--vorlage", action="store_true", help="eine leere Vergleichsdatei ausgeben")
    args = parser.parse_args(argv)

    if args.vorlage:
        print(VORLAGE, end="")
        return 0
    if not args.datei:
        parser.error("entweder eine Datei oder --vorlage")

    try:
        ergebnis = vergleiche(Path(args.datei).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Datei nicht gefunden: {args.datei}", file=sys.stderr)
        return 2
    except VergleichsDateiFehler as exc:
        print(f"Die Vergleichsdatei stimmt nicht: {exc}", file=sys.stderr)
        return 2
    except LohnKonfigurationFehlt as exc:
        print("Unsere Engine rechnet nicht, weil Eingaben fehlen:", file=sys.stderr)
        for fehlt in exc.fehlend:
            print(f"  · {fehlt}", file=sys.stderr)
        print("\nDas ist Absicht: ein geschätzter Satz sieht aus wie ein richtiger.", file=sys.stderr)
        return 2

    print(bericht(ergebnis))
    return 0 if ergebnis.stimmt else 1


if __name__ == "__main__":
    raise SystemExit(main())
