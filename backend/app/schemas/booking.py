"""Booking schemas."""

from pydantic import BaseModel

from app.schemas.common import Money


class BookingCreate(BaseModel):
    datum: str = ""
    beleg: str = ""
    rechnung: str = ""
    beschreibung: str = ""
    kt_soll: str = ""
    kt_haben: str = ""
    betrag_chf: Money | None = None
    mwst_code: str = ""
    art_betrag: str = ""
    mwst_pct: str = ""
    mwst_chf: Money | None = None
    ks3: str = ""
    source: str = "kontoauszug"


class BookingResponse(BookingCreate):
    id: int
    tenant_id: int

    class Config:
        from_attributes = True


class BookingStatsResponse(BaseModel):
    total_count: int
    total_amount: Money
    #: Rows per `source` ("kontoauszug", "scanner", "billing", … and "unknown").
    by_source: dict[str, int]
