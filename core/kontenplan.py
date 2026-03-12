"""
Dynamic Kontenplan manager with JSON persistence.

Provides a central place to load, edit, and save:
  - kontenplan.json     → account number → name mapping
  - konto_defaults.json → KontoSoll → {KontoHaben, MwStCode, MwStUStProz}
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KONTENPLAN_PATH = DATA_DIR / "kontenplan.json"
DEFAULTS_PATH = DATA_DIR / "konto_defaults.json"

DATA_DIR.mkdir(exist_ok=True)

# ── Minimal fallback Kontenplan ──────────────────────────────────────────────

_FALLBACK_KONTENPLAN = {
    "1000": "Kasse",
    "1020": "Bankguthaben",
    "1100": "Forderungen aus Leistungen (Debitoren)",
    "2000": "Kreditoren (Verbindlichkeiten aus L+L)",
    "2200": "Geschuldete MWST (Umsatzsteuer)",
    "3000": "Bruttoertrag Arbeit",
    "4000": "Materialaufwand Produktion",
    "5000": "Lohnaufwand",
    "5700": "AHV, IV, EO",
    "6000": "Raumaufwand",
    "6200": "Fahrzeugaufwand",
    "6210": "Betriebsstoffe",
    "6500": "Verwaltungsaufwand",
    "6570": "EDV Updates, Lizenzen, Wartung",
    "6900": "Finanzaufwand",
    "8900": "Direkte Steuern",
}


# ── Kontenplan Manager ───────────────────────────────────────────────────────

class KontenplanManager:
    """Thread-safe Kontenplan manager backed by JSON files."""

    def __init__(self):
        self._plan: dict[str, str] = {}
        self._load()

    def _load(self):
        if KONTENPLAN_PATH.exists():
            with open(KONTENPLAN_PATH, "r", encoding="utf-8") as f:
                self._plan = json.load(f)
        else:
            self._plan = dict(_FALLBACK_KONTENPLAN)
            self.save()

    def save(self):
        with open(KONTENPLAN_PATH, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(self._plan.items())), f, ensure_ascii=False, indent=2)

    @property
    def plan(self) -> dict[str, str]:
        return dict(self._plan)

    def get(self, konto: str, default: str = "") -> str:
        return self._plan.get(konto, default)

    def set(self, konto: str, name: str):
        self._plan[konto] = name

    def delete(self, konto: str):
        self._plan.pop(konto, None)

    def update_from_dict(self, data: dict[str, str]):
        """Replace the entire Kontenplan with new data and save."""
        self._plan = {k: v for k, v in data.items() if k.strip() and v.strip()}
        self.save()

    def __len__(self):
        return len(self._plan)

    def __contains__(self, konto: str):
        return konto in self._plan


# ── Konto defaults helpers ───────────────────────────────────────────────────

def load_konto_defaults() -> dict:
    """Load default account mappings (KontoSoll → KontoHaben, MwSt)."""
    if DEFAULTS_PATH.exists():
        with open(DEFAULTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_konto_defaults(defaults: dict):
    """Save default account mappings to JSON."""
    with open(DEFAULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(defaults, f, ensure_ascii=False, indent=2)
