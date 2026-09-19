"""LohnSettings — the social-insurance rates one tenant pays (B-72).

A Swiss payslip is arithmetic, but the numbers in it come from four different
places, and only two of them are the same for every employer in the country:

* **AHV/IV/EO and ALV** are set by federal law. Every employer deducts the same
  percentage, so those carry a default here.
* **UVG, UVGZ and KTG** come from the contract with the insurer. Two companies
  in the same street pay different rates.
* **FAK** is cantonal, and the Ausgleichskasse's Verwaltungskostenbeitrag is
  per-Kasse.
* **BVG** is per employee — see ``Mitarbeiter``, not here.

Everything in the second and third group is nullable and has no default. A
payslip that needs a missing rate is refused rather than estimated: a wrong
Lohnausweis is a problem with the tax office, not a rounding difference.

One row per tenant, never shared.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import Chf

# Statutory, identical for every employer (AHVG/AVIG). Employee share only —
# the employer pays the same again, which is how the engine derives it.
AHV_SATZ_AN = 5.3  # AHV + IV + EO, Arbeitnehmeranteil
ALV_SATZ_AN = 1.1  # Arbeitslosenversicherung, Arbeitnehmeranteil
ALV_JAHRESGRENZE = 148_200.0  # UVG-Höchstlohn; above it no ALV is owed

#: Shown next to the federal rates, the way B-70 and B-71 show theirs. A rate
#: without a source and a date is a number somebody eventually believes; these
#: two change by law and the review date is the point of the sentence.
_ALV_GRENZE_TEXT = f"{ALV_JAHRESGRENZE:,.0f}".replace(",", "'")
LOHN_QUELLE = (
    "AHV/IV/EO 10.6 % (5.3 % je Seite, ohne Höchstlohn) und ALV 2.2 % "
    f"(1.1 % je Seite bis CHF {_ALV_GRENZE_TEXT}) — gesetzlich, für alle Arbeitgeber gleich. "
    "Quellen: AHV/IV Merkblatt 2.01 und 2.08. Stand geprüft: September 2026; "
    "die Ansätze werden jeweils im Januar neu festgelegt."
)

# KMU Kontenrahmen (services/tenant_setup.py).
KONTO_LOHNAUFWAND = "5000"
KONTO_SOZIALVERSICHERUNG = "5700"
KONTO_VERBINDLICHKEIT = "2270"  # Kontokorrent Sozialversicherungen
KONTO_BANK = "1020"


class LohnSettings(Base):
    __tablename__ = "lohn_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_lohn_settings_tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    # Federal, defaulted.
    ahv_satz_an: Mapped[float] = mapped_column(Float, default=AHV_SATZ_AN)
    alv_satz_an: Mapped[float] = mapped_column(Float, default=ALV_SATZ_AN)
    alv_jahresgrenze: Mapped[float] = mapped_column(Chf, default=ALV_JAHRESGRENZE)

    # From the insurance contract. None = not on file; the engine refuses.
    uvg_bu_satz: Mapped[float | None] = mapped_column(Float, nullable=True)  # Berufsunfall, AG zahlt
    uvg_nbu_satz: Mapped[float | None] = mapped_column(Float, nullable=True)  # Nichtberufsunfall, AN zahlt
    uvgz_satz_an: Mapped[float | None] = mapped_column(Float, nullable=True)  # Zusatzversicherung, AN-Anteil
    uvgz_satz_ag: Mapped[float | None] = mapped_column(Float, nullable=True)
    ktg_satz_an: Mapped[float | None] = mapped_column(Float, nullable=True)  # Krankentaggeld, AN-Anteil
    ktg_satz_ag: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cantonal / per Ausgleichskasse, employer only.
    fak_satz: Mapped[float | None] = mapped_column(Float, nullable=True)
    verwaltungskosten_satz: Mapped[float | None] = mapped_column(Float, nullable=True)

    konto_lohnaufwand: Mapped[str] = mapped_column(String(20), default=KONTO_LOHNAUFWAND)
    konto_sozialversicherung: Mapped[str] = mapped_column(String(20), default=KONTO_SOZIALVERSICHERUNG)
    konto_verbindlichkeit: Mapped[str] = mapped_column(String(20), default=KONTO_VERBINDLICHKEIT)
    konto_bank: Mapped[str] = mapped_column(String(20), default=KONTO_BANK)

    # Rule 5 of docs/B-72-LOHN-SPEC.md: until one real month has been checked
    # against what the customer's previous payroll produced, every payslip is
    # printed with a "Nicht für die Einreichung" watermark. False by default —
    # the sign-off is a human act, and nothing in this app can perform it.
    freigegeben: Mapped[bool] = mapped_column(Boolean, default=False)
    freigegeben_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
