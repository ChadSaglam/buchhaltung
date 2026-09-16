"""Dauerbuchungen (B-74)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class DauerbuchungOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    betrag: float
    #: In how many distinct months this amount was paid.
    monate: int
    letzter_monat: str
    konto: str
    #: The day of the month it usually leaves on.
    tag: int
    #: bezahlt | offen | fehlt — for the current month.
    status: str
    faellig_am: date | None = None
    tage_ueberfaellig: int = 0
    schluessel: str = ""


class DauerbuchungenResponse(BaseModel):
    stichtag: date
    monat: str
    eintraege: list[DauerbuchungOut] = []
    #: Only the ones whose usual day has passed with nothing booked.
    fehlen: list[DauerbuchungOut] = []
    #: What is still to leave the account this month (open + missing).
    offen_total: float = 0.0
    #: The whole monthly bill, whether or not it has gone out yet.
    monatstotal: float = 0.0
