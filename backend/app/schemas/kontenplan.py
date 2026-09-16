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


class KontenplanResponse(BaseModel):
    """Account number → description, as the Kontenplan editor reads it."""

    kontenplan: dict[str, str]


class KontenplanSaved(BaseModel):
    status: str
    count: int


class KontoDefaultOut(BaseModel):
    """Default counter-account and VAT for one debit account.

    The keys are the Banana column names the import/export speak, so they stay
    capitalised on the wire.
    """

    KontoHaben: str
    MwStCode: str
    MwStUStProz: str


class KontoDefaultsResponse(BaseModel):
    defaults: dict[str, KontoDefaultOut]
