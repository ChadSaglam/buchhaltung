"""Lohnabrechnung — one payslip, frozen (B-72).

The important property of this table is that it stores the *rates* next to the
amounts. A payslip is not a view over today's settings: when the UVG premium
changes in January, December's payslip must still show what December actually
deducted, because that is the number that went to the Ausgleichskasse and that
is the number on the Lohnausweis. Recomputing from current settings would
quietly rewrite the past.

So: once ``abgerechnet_am`` is set the row is read-only. A mistake is corrected
by a new payslip, the same way a wrong booking is corrected by a counter-booking
rather than by editing the old one.

Employer contributions live here too. They never touch the employee's net pay,
but they are the other half of the 5700 booking and of the Ausgleichskasse's
yearly reconciliation, so they belong on the same row as the month they are for.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import Chf

STATUS_ENTWURF = "entwurf"
STATUS_ABGERECHNET = "abgerechnet"


class Lohnabrechnung(Base):
    __tablename__ = "lohnabrechnungen"
    # One payslip per employee per month. A correction is a new month's row or a
    # deleted draft, never a second row for the same period.
    __table_args__ = (
        UniqueConstraint("tenant_id", "mitarbeiter_id", "jahr", "monat", name="uq_lohnabrechnung_periode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    mitarbeiter_id: Mapped[int] = mapped_column(ForeignKey("mitarbeiter.id", ondelete="CASCADE"), index=True)

    jahr: Mapped[int] = mapped_column(Integer)
    monat: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_ENTWURF)

    # Earnings.
    grundlohn: Mapped[float] = mapped_column(Chf, default=0)
    # B-100: how the Grundlohn was arrived at. Both 0 for a monthly employee.
    # Hours are a count, not money, so `stunden` is a plain Float.
    stunden: Mapped[float] = mapped_column(Float, default=0)
    stundenlohn: Mapped[float] = mapped_column(Chf, default=0)
    dreizehnter: Mapped[float] = mapped_column(Chf, default=0)
    zulagen: Mapped[float] = mapped_column(Chf, default=0)  # AHV-pflichtig (Gratifikation, Bonus)
    kinderzulagen: Mapped[float] = mapped_column(Chf, default=0)  # B-96: AHV-frei
    brutto: Mapped[float] = mapped_column(Chf, default=0)  # what is paid: ahv_lohn + kinderzulagen
    # B-96: the contributory base every rate is applied to, and what the ALV
    # ceiling accumulates over. Stored, not derived, so a later change to what
    # counts as AHV-frei never rewrites a settled month.
    ahv_lohn: Mapped[float] = mapped_column(Chf, default=0)

    # Employee deductions — rate *and* amount, so the payslip stays readable
    # without the settings row it was computed from.
    ahv_satz: Mapped[float] = mapped_column(Float, default=0)
    ahv_betrag: Mapped[float] = mapped_column(Chf, default=0)
    alv_satz: Mapped[float] = mapped_column(Float, default=0)
    alv_betrag: Mapped[float] = mapped_column(Chf, default=0)
    alv_basis: Mapped[float] = mapped_column(Chf, default=0)  # capped gross, may be < brutto
    nbu_satz: Mapped[float] = mapped_column(Float, default=0)
    nbu_betrag: Mapped[float] = mapped_column(Chf, default=0)
    uvgz_satz: Mapped[float] = mapped_column(Float, default=0)
    uvgz_betrag: Mapped[float] = mapped_column(Chf, default=0)
    ktg_satz: Mapped[float] = mapped_column(Float, default=0)
    ktg_betrag: Mapped[float] = mapped_column(Chf, default=0)
    bvg_betrag: Mapped[float] = mapped_column(Chf, default=0)
    quellensteuer_satz: Mapped[float] = mapped_column(Float, default=0)
    quellensteuer_betrag: Mapped[float] = mapped_column(Chf, default=0)

    abzuege: Mapped[float] = mapped_column(Chf, default=0)
    netto: Mapped[float] = mapped_column(Chf, default=0)

    # Employer contributions.
    ag_ahv: Mapped[float] = mapped_column(Chf, default=0)
    ag_alv: Mapped[float] = mapped_column(Chf, default=0)
    ag_bu: Mapped[float] = mapped_column(Chf, default=0)
    ag_uvgz: Mapped[float] = mapped_column(Chf, default=0)
    ag_ktg: Mapped[float] = mapped_column(Chf, default=0)
    ag_fak: Mapped[float] = mapped_column(Chf, default=0)
    ag_verwaltungskosten: Mapped[float] = mapped_column(Chf, default=0)
    ag_bvg: Mapped[float] = mapped_column(Chf, default=0)
    ag_total: Mapped[float] = mapped_column(Chf, default=0)

    abgerechnet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def periode(self) -> str:
        return f"{self.jahr:04d}-{self.monat:02d}"

    @property
    def gesperrt(self) -> bool:
        """True once issued: the row may no longer change."""
        return self.status == STATUS_ABGERECHNET
