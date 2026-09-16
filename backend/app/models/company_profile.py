"""CompanyProfile — who *we* are on an invoice we write ourselves (B-68).

Everything the system knew until now came from documents other people sent us.
Writing a QR-Rechnung turns that around: the Zahlteil needs our IBAN, our name
and our address, and the booking needs to know which accounts revenue lands on.
One row per tenant, never shared.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Swiss defaults — the KMU Kontenrahmen numbers and the Banana VAT code for
# revenue at the normal rate (see services/tenant_setup.py).
KONTO_DEBITOREN = "1100"
KONTO_ERTRAG = "3000"
KONTO_BANK = "1020"
MWST_CODE_UMSATZ = "V81"
MWST_PCT_UMSATZ = "-8.10"
DEFAULT_TERMS_DAYS = 30


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_company_profiles_tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    # Absender on the letter and creditor in the QR payload.
    name: Mapped[str] = mapped_column(String(70), default="")
    strasse: Mapped[str] = mapped_column(String(70), default="")
    hausnummer: Mapped[str] = mapped_column(String(16), default="")
    plz: Mapped[str] = mapped_column(String(16), default="")
    ort: Mapped[str] = mapped_column(String(35), default="")
    land: Mapped[str] = mapped_column(String(2), default="CH")

    iban: Mapped[str] = mapped_column(String(34), default="")
    mwst_nr: Mapped[str] = mapped_column(String(32), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    telefon: Mapped[str] = mapped_column(String(50), default="")

    zahlungsfrist_tage: Mapped[int] = mapped_column(Integer, default=DEFAULT_TERMS_DAYS)
    konto_debitoren: Mapped[str] = mapped_column(String(20), default=KONTO_DEBITOREN)
    konto_ertrag: Mapped[str] = mapped_column(String(20), default=KONTO_ERTRAG)
    konto_bank: Mapped[str] = mapped_column(String(20), default=KONTO_BANK)
    mwst_code: Mapped[str] = mapped_column(String(10), default=MWST_CODE_UMSATZ)
    mwst_pct: Mapped[str] = mapped_column(String(10), default=MWST_PCT_UMSATZ)

    # B-71: effektiver Gewinnsteuersatz in Prozent, wie ihn der Treuhänder nennt.
    # None = nicht hinterlegt; dann wird nichts geschätzt (Kanton *und* Gemeinde
    # bestimmen den Satz, ein Vorgabewert wäre eine Zahl, der jemand glaubt).
    gewinnsteuer_satz: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
