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
        # B-28, measured on 800k rows across 200 tenants: without this the list
        # query walks the primary key backwards and throws away 23'053 rows to
        # find 100 — linear in the number of tenants. With it, an Index Cond:
        # 438 buffers → 90, and flat.
        Index("ix_bookings_tenant_id_id", "tenant_id", "id"),
        # The same list with ?source=receipt: 327 buffers and 16'715 rows
        # discarded → 88 buffers and none, because the filter moves into the index.
        Index("ix_bookings_tenant_source_id", "tenant_id", "source", "id"),
        Index(
            "uq_bookings_billing_source_key",
            "tenant_id",
            "source_key",
            unique=True,
            postgresql_where=text("source = 'billing'"),
            sqlite_where=text("source = 'billing'"),
        ),
    )

    # No `index=True`: the primary key already is a unique B-tree on this
    # column, so `ix_bookings_id` was a second copy of it that every INSERT had
    # to maintain. Dropped in B-28 with no query getting slower.
    id = Column(Integer, primary_key=True)
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
