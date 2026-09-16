"""Was ein Abo enthält (B-23).

**Die Zahlen in ``PLANS`` sind eine Geschäftsentscheidung, keine technische.**
Sie stehen bewusst alle in dieser einen Tabelle: wer sie ändern will, ändert
sie hier und nirgends sonst. Der Mechanismus ist B-23 — die Höhe der Grenzen
gehört dem Eigentümer.

Gezählt wird ausschliesslich aus ``usage_events`` (B-54 hat die Tabelle
eingeführt). Das heisst: eine Grenze existiert nur, wenn der Schreibpfad ein
Ereignis schreibt. Eine Grenze ohne Ereignis ist eine Lüge, deshalb hält
``tests/test_plan_limits.py`` beide Seiten gegeneinander.

``None`` heisst *unbegrenzt* — nicht null.
"""

from __future__ import annotations

from typing import Final

#: Monatlich zurückgesetzte Zähler (Kalendermonat, Zeitzone unten).
MONATLICH: Final = ("belege", "klassifizierungen")
#: Bestandsgrössen — laufen nicht ab, werden nur beim Löschen kleiner.
BESTAND: Final = ("speicher_mb",)

LIMIT_KEYS: Final[tuple[str, ...]] = MONATLICH + BESTAND

#: Der Monat ist ein Schweizer Kalendermonat, kein UTC-Monat. Ein Beleg, der am
#: 1. Februar um 00:30 Uhr in Zürich hochgeladen wird, gehört in den Februar —
#: in UTC wäre er noch Januar, und der Kunde sähe eine Grenze, die er nicht
#: erreicht hat.
ZEITZONE: Final = "Europe/Zurich"

#: Welches Ereignis in ``usage_events`` welchen Zähler füttert.
EVENT_TYPE: Final[dict[str, str]] = {
    "belege": "beleg",
    "klassifizierungen": "classify",
    "speicher_mb": "storage_bytes",
}

#: -----------------------------------------------------------------------
#: DIE ZAHLEN. Hier ändern.
#: -----------------------------------------------------------------------
#: `free` ist absichtlich gross genug, dass ein echter Kleinbetrieb damit
#: arbeiten kann — eine Grenze, die beim ersten ernsthaften Monat zuschlägt,
#: ist ein Verkaufsgespräch, das man nicht führen will. `pro` ist unbegrenzt,
#: bis es einen Grund gibt, das zu ändern.
PLANS: Final[dict[str, dict[str, int | None]]] = {
    "free": {
        "belege": 100,
        "klassifizierungen": 500,
        "speicher_mb": 1024,
    },
    "pro": {
        "belege": None,
        "klassifizierungen": None,
        "speicher_mb": 25_600,
    },
    "enterprise": {
        "belege": None,
        "klassifizierungen": None,
        "speicher_mb": None,
    },
}

#: Ein unbekannter Plan-String (die Plattform darf jederzeit einen neuen
#: erfinden) wird wie `free` behandelt — nie wie `unbegrenzt`.
PLAN_FALLBACK: Final = "free"

#: Ab wie viel Prozent die Oberfläche warnt, bevor die Wand kommt.
WARNSCHWELLE: Final = 0.8

#: Menschenlesbare Namen für die Fehlermeldung.
LIMIT_LABEL: Final[dict[str, str]] = {
    "belege": "Belege pro Monat",
    "klassifizierungen": "Klassifizierungen pro Monat",
    "speicher_mb": "Speicherplatz (MB)",
}


def limits_for(plan: str | None) -> dict[str, int | None]:
    """Die Grenzen eines Plans. Unbekannt → `free`, nie unbegrenzt."""
    return dict(PLANS.get((plan or "").strip().lower(), PLANS[PLAN_FALLBACK]))
