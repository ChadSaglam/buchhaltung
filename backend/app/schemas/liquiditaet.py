"""Liquidität und Steuerrückstellung (B-71)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    datum: date
    label: str
    #: Positive = money coming in, negative = going out.
    betrag: float
    #: debitor | kreditor | dauerbuchung
    quelle: str
    document_id: int | None = None
    ueberfaellig: bool = False


class DauerbuchungOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    betrag: float
    #: In how many distinct months this amount was paid.
    monate: int
    letzter_monat: str
    konto: str


class MonatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schluessel: str
    label: str
    eingang: float
    ausgang: float
    saldo_ende: float


class SteuerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jahr: int
    ertrag: float
    aufwand: float
    gewinn: float
    #: None when the tenant has not entered a rate — then nothing is estimated.
    satz: float | None = None
    rueckstellung_soll: float | None = None
    schon_zurueckgestellt: float = 0.0
    offen: float | None = None
    pro_quartal: float | None = None
    quelle: str = ""
    hinweis: str = ""


class LiquiditaetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stichtag: date
    bis: date
    stand_heute: float
    eingang: float
    ausgang: float
    prognose: float
    #: The lowest the running balance gets inside the window — the number that hurts.
    tiefster_stand: float
    tiefster_am: date
    positionen: list[PositionOut] = []
    dauerbuchungen: list[DauerbuchungOut] = []
    monate: list[MonatOut] = []
    warnungen: list[str] = []
    steuer: SteuerOut | None = None
