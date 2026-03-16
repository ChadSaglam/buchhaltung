"""SQLAlchemy model for bookings."""
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.models.base import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    datum = Column(String, default="")
    beleg = Column(String, default="")
    rechnung = Column(String, default="")
    beschreibung = Column(String, default="")
    kt_soll = Column(String, default="")
    kt_haben = Column(String, default="")
    betrag = Column(Float, default=0)
    mwst_code = Column(String, default="")
    mwst_pct = Column(String, default="")
    mwst_amount = Column(Float, default=0)
    source = Column(String, default="")