"""Kontenplan schemas."""
from pydantic import BaseModel


class KontoEntry(BaseModel):
    konto_nr: str
    beschreibung: str


class KontoDefaultEntry(BaseModel):
    konto_soll: str
    konto_haben: str = "1020"
    mwst_code: str = ""
    mwst_pct: str = ""
