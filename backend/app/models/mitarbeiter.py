"""Mitarbeiter — one employee, as payroll needs to know them (B-72).

Deliberately not an HR record. Everything here is a number that appears on a
payslip or decides whether a deduction applies; anything that does not (address,
contract, holiday balance) stays out, because storing it would make this a
personnel file with the duties that come with one.

Two fields are worth a note:

* ``bvg_an_monat`` / ``bvg_ag_monat`` are *amounts*, not rates. The pension fund
  computes the Altersgutschrift from age, insured salary and its own plan, then
  sends a statement per employee. Re-deriving it here from Koordinationsabzug
  and Altersgutschriftensätze would produce a number that disagrees with the
  fund's, and the fund's is the one that gets paid.
* ``quellensteuer_satz`` is likewise a number the cantonal tariff gives for this
  person's Tarifcode, civil status and children. The tariff tables are cantonal
  data we do not ship. Flag set and rate missing ⇒ the payslip is refused.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import Chf

PENSUM_VOLL = 100.0


class Mitarbeiter(Base):
    __tablename__ = "mitarbeiter"
    __table_args__ = (Index("ix_mitarbeiter_tenant_aktiv", "tenant_id", "austritt"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    vorname: Mapped[str] = mapped_column(String(100), default="")
    name: Mapped[str] = mapped_column(String(100), default="")
    ahv_nummer: Mapped[str] = mapped_column(String(20), default="")  # 756.xxxx.xxxx.xx
    geburtsdatum: Mapped[date | None] = mapped_column(Date, nullable=True)

    eintritt: Mapped[date | None] = mapped_column(Date, nullable=True)
    austritt: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = still employed

    pensum: Mapped[float] = mapped_column(Float, default=PENSUM_VOLL)
    monatslohn: Mapped[float] = mapped_column(Chf, default=0)  # gross for a full month at this Pensum
    dreizehnter: Mapped[bool] = mapped_column(Boolean, default=False)
    kinder: Mapped[int] = mapped_column(Integer, default=0)
    # B-96: Familienzulagen are paid with the salary and are NOT part of the
    # massgebender Lohn — no AHV, ALV, UVG, KTG, FAK on them (AHVV Art. 6). A
    # monthly total rather than per child, because the cantonal rate per child
    # differs and the Ausgleichskasse's decision names the amount, not a formula.
    kinderzulagen_monat: Mapped[float] = mapped_column(Chf, default=0)
    kanton: Mapped[str] = mapped_column(String(2), default="")

    quellensteuer: Mapped[bool] = mapped_column(Boolean, default=False)
    quellensteuer_satz: Mapped[float | None] = mapped_column(Float, nullable=True)
    quellensteuer_tarif: Mapped[str] = mapped_column(String(10), default="")

    # From the pension fund's statement, per employee, per month.
    bvg_an_monat: Mapped[float | None] = mapped_column(Chf, nullable=True)
    bvg_ag_monat: Mapped[float | None] = mapped_column(Chf, nullable=True)

    iban: Mapped[str] = mapped_column(String(34), default="")
    email: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def anzeige_name(self) -> str:
        return f"{self.vorname} {self.name}".strip()
