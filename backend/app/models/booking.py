"""SQLAlchemy model for bookings."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, text

from app.models.base import Base
from app.models.types import Chf


class Booking(Base):
    __tablename__ = "bookings"
    # B-52: two concurrent `invoice.paid` deliveries used to create two bookings,
    # because the check was a SELECT and the race sat between it and the INSERT.
    # The database decides now; the service turns the IntegrityError into
    # "duplicate". Partial, so ordinary bookings may repeat a source_key.
    __table_args__ = (
        Index(
            "uq_bookings_billing_source_key",
            "tenant_id",
            "source_key",
            unique=True,
            postgresql_where=text("source = 'billing'"),
            sqlite_where=text("source = 'billing'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    datum = Column(String, default="")
    beleg = Column(String, default="")
    rechnung = Column(String, default="")
    beschreibung = Column(String, default="")
    kt_soll = Column(String, default="")
    kt_haben = Column(String, default="")
    betrag = Column(Chf, default=0)
    mwst_code = Column(String, default="")
    mwst_pct = Column(String, default="")
    mwst_amount = Column(Chf, default=0)
    source = Column(String, default="")
    # Storage key of the document this booking came from (services/receipts.py); None for manual rows.
    source_key = Column(String(255), nullable=True)
    # Banana hand-off (phase 4): set once the booking left in a batch, so it never leaves twice.
    export_batch_id = Column(Integer, ForeignKey("export_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    exported_at = Column(DateTime(timezone=True), nullable=True)
