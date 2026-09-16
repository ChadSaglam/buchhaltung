"""Verbrauch gegen Plan-Grenzen (B-23).

Ein Zähler statt zweier Formen: `limit = null` heisst unbegrenzt, `anteil =
null` dann ebenfalls. Die Oberfläche soll nicht raten müssen, ob eine fehlende
Zahl "kein Limit" oder "noch nicht geladen" bedeutet.
"""

from __future__ import annotations

from pydantic import BaseModel


class UsageCounter(BaseModel):
    key: str
    label: str
    benutzt: int
    limit: int | None
    #: 0.0–1.0, oder null wenn unbegrenzt.
    anteil: float | None
    warnung: bool
    erreicht: bool
    #: "monat" = setzt sich am Monatsersten zurück, "bestand" = nicht.
    periode: str


class UsageResponse(BaseModel):
    plan: str
    #: False heisst: gezählt und angezeigt, aber niemand wird abgelehnt.
    durchgesetzt: bool
    monat_seit: str
    zaehler: list[UsageCounter]
