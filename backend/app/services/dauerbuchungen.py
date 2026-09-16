"""Dauerbuchungen — was jeden Monat gleich abgeht (B-74).

Erkannt, nicht getippt. Miete, Leasing und Versicherung stehen in den eigenen
Buchungen; wer sie nochmals in ein Formular tippt, hat zwei Wahrheiten. Der
Schlüssel ist der normalisierte Text (``preprocess``: ohne Monatsnamen, ohne
Ziffern), damit "Miete Januar" und "Miete Februar" dieselbe Zahlung sind.

B-71 rechnet damit die Liquidität. Was hier dazukommt, ist die andere Hälfte:
**welche davon diesen Monat fehlt**. "Cembra 770.60 fehlt diesen Monat" ist
eine Frage, die sonst erst beim Abschluss auffällt — oder beim Mahnbrief.

Die Ehrlichkeit dabei: eine Zahlung, deren üblicher Tag noch nicht erreicht
ist, *fehlt* nicht, sie ist nur noch nicht fällig. Der Unterschied steht im
Status, nicht im Weglassen.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.models.booking import Booking
from app.services.classifier import preprocess
from app.services.documents import parse_date
from app.services.export import round_chf

# Eine Zahlung gilt als monatlich wiederkehrend, wenn sie in so vielen
# verschiedenen Monaten auftaucht …
MIN_MONATE = 3
# … und der Betrag um höchstens so viel schwankt (Versicherungsprämien ändern).
TOLERANZ = 0.15
# So weit wird zurückgeschaut.
FENSTER_MONATE = 12
# So viele Tage nach dem üblichen Zahltag gilt eine Zahlung als überfällig,
# statt als "kommt noch". Ein Lastschriftdatum wandert um ein Wochenende herum.
KULANZ_TAGE = 3

# KMU-Kontenrahmen, Gruppe 10 "Flüssige Mittel" (ohne 106 Wertschriften).
LIQUIDE_PRAEFIXE = ("100", "101", "102", "103", "104", "105")

STATUS_BEZAHLT = "bezahlt"
STATUS_OFFEN = "offen"
STATUS_FEHLT = "fehlt"

_ZAHL_RE = re.compile(r"\d")


def chf(value) -> float:
    return float(round_chf(value))


def liquide(konto: str) -> bool:
    return (konto or "").startswith(LIQUIDE_PRAEFIXE)


def monatsschluessel(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


@dataclass
class Dauerbuchung:
    """Ein Betrag, der jeden Monat gleich abgeht — aus den Buchungen erkannt."""

    label: str
    betrag: float
    monate: int
    letzter_monat: str
    konto: str
    #: Der Tag im Monat, an dem sie üblicherweise abgeht (Median der Tage).
    tag: int = 1
    #: bezahlt | offen | fehlt — für den laufenden Monat.
    status: str = STATUS_OFFEN
    #: Wann sie diesen Monat erwartet wird (oder erwartet wurde).
    faellig_am: date | None = None
    #: Wie viele Tage überfällig, wenn `status == "fehlt"`.
    tage_ueberfaellig: int = 0
    #: Der normalisierte Schlüssel, unter dem sie erkannt wurde.
    schluessel: str = ""
    monatsliste: list[str] = field(default_factory=list)


def _tag_im_monat(jahr: int, monat: int, tag: int) -> date:
    """`tag` in that month, clamped — the 31st of February is the 28th/29th."""
    erster_naechster = date(jahr + 1, 1, 1) if monat == 12 else date(jahr, monat + 1, 1)
    letzter = erster_naechster - timedelta(days=1)
    return date(jahr, monat, min(tag, letzter.day))


def erkennen(bookings: list[Booking], heute: date) -> list[Dauerbuchung]:
    """Die wiederkehrenden Abgänge, mit Status für den laufenden Monat.

    Erkannt wird nur, was Geld *kostet* — eine Einnahme, die jeden Monat kommt,
    ist ein Kunde und keine Dauerbuchung.
    """
    fenster_ab = heute - timedelta(days=31 * FENSTER_MONATE)
    gruppen: dict[str, list[tuple[date, float, str, str]]] = defaultdict(list)

    for b in bookings:
        betrag = float(b.betrag or 0)
        if betrag <= 0 or not liquide(b.kt_haben):
            continue  # kein Abgang vom Konto
        d = parse_date(b.datum)
        if d is None or d < fenster_ab or d > heute:
            continue
        key = preprocess(b.beschreibung or "")
        if len(key) < 3:
            continue
        gruppen[key].append((d, betrag, (b.beschreibung or "").strip(), b.kt_soll or ""))

    dieser_monat = monatsschluessel(heute)
    erkannt: list[Dauerbuchung] = []

    for key, eintraege in gruppen.items():
        monate = sorted({monatsschluessel(d) for d, _b, _t, _k in eintraege})
        if len(monate) < MIN_MONATE:
            continue
        betraege = [b for _d, b, _t, _k in eintraege]
        mitte = median(betraege)
        if mitte <= 0:
            continue
        # Ein Betrag, der wild schwankt, ist keine Dauerbuchung.
        if any(abs(b - mitte) / mitte > TOLERANZ for b in betraege):
            continue

        label = max((t for _d, _b, t, _k in eintraege), key=len)
        konto = next((k for _d, _b, _t, k in eintraege if k), "")
        tag = int(median([float(d.day) for d, _b, _t, _k in eintraege]))
        faellig = _tag_im_monat(heute.year, heute.month, tag)

        if dieser_monat in monate:
            status, ueberfaellig = STATUS_BEZAHLT, 0
        elif heute <= faellig + timedelta(days=KULANZ_TAGE):
            status, ueberfaellig = STATUS_OFFEN, 0
        else:
            status, ueberfaellig = STATUS_FEHLT, (heute - faellig).days

        erkannt.append(
            Dauerbuchung(
                label=_ZAHL_RE.sub("", label).strip(" -–—.,") or label,
                betrag=chf(mitte),
                monate=len(monate),
                letzter_monat=monate[-1],
                konto=konto,
                tag=tag,
                status=status,
                faellig_am=faellig,
                tage_ueberfaellig=ueberfaellig,
                schluessel=key,
                monatsliste=monate,
            )
        )

    # Was fehlt zuerst, dann was noch kommt, dann was erledigt ist — und
    # innerhalb jeder Gruppe das Teuerste oben.
    rang = {STATUS_FEHLT: 0, STATUS_OFFEN: 1, STATUS_BEZAHLT: 2}
    erkannt.sort(key=lambda d: (rang.get(d.status, 9), -d.betrag))
    return erkannt


def fehlende(dauer: list[Dauerbuchung]) -> list[Dauerbuchung]:
    """Only the ones whose usual day has passed without a booking."""
    return [d for d in dauer if d.status == STATUS_FEHLT]


def summe_offen(dauer: list[Dauerbuchung]) -> float:
    """What is still to go out this month — the open and the missing together."""
    return chf(sum(d.betrag for d in dauer if d.status != STATUS_BEZAHLT))


def passende(dauer: list[Dauerbuchung], *, betrag: float, tag: date | None = None) -> Dauerbuchung | None:
    """The recurring payment an unmatched bank line of `betrag` most likely is.

    Amount within the same tolerance the detection uses, and — when a date is
    given — within a month of the usual day. Returns None rather than a guess,
    because this answer becomes a booking proposal.
    """
    ziel = abs(float(betrag or 0))
    if ziel <= 0:
        return None
    treffer = [d for d in dauer if d.betrag > 0 and abs(d.betrag - ziel) / d.betrag <= TOLERANZ]
    if tag is not None:
        treffer = [d for d in treffer if abs((_tag_im_monat(tag.year, tag.month, d.tag) - tag).days) <= 15]
    if len(treffer) != 1:
        return None  # ambiguous is not a match
    return treffer[0]
