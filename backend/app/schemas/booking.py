"""Booking schemas."""
from pydantic import BaseModel


class BookingCreate(BaseModel):
    datum: str = ""
    beleg: str = ""
    rechnung: str = ""
    beschreibung: str = ""
    kt_soll: str = ""
    kt_haben: str = ""
    betrag_chf: float | None = None
    mwst_code: str = ""
    art_betrag: str = ""
    mwst_pct: str = ""
    mwst_chf: float | None = None
    ks3: str = ""
    source: str = "kontoauszug"


class BookingResponse(BookingCreate):
    id: int
    tenant_id: int

    class Config:
        from_attributes = True
