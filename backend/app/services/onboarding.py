"""The first ten seconds (B-20).

A new tenant's first run has one job: drop a file, see a result. That is rule 3
of `docs/IA-2026-09-14.md` — no settings before value — and it fails at the
first step for the most ordinary reason imaginable: **they do not have a Swiss
QR invoice on the laptop they are signing up on.**

So this generates one. A complete, scannable QR-Rechnung from fictional data,
rendered by the same `rechnung_pdf` the product uses for real invoices, which
means the sample exercises the actual pipeline rather than a special case:
`qr_bill.py` decodes the Swiss Payments Code out of it exactly the way it would
from a supplier's bill, and what the user sees on screen is the real behaviour.

**It is a download, not a seeded row.** Creating demo documents inside a real
tenant would mean inventing a way to remove them again, and a bookkeeping system
that quietly writes rows nobody asked for is exactly the kind of thing an
accountant stops trusting. The user drops it in themselves; from that moment it
is an ordinary document they can handle or delete like any other.

Everything here is fictional and says so on the page. The IBAN is SIX's own
documentation example (`CH44 3199 9123 0008 8901 2`), not an account that can
receive money.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.models.company_profile import CompanyProfile
from app.models.document import DIRECTION_EINGANG, KIND_RECHNUNG, Document
from app.models.invoice_position import InvoicePosition
from app.services import swiss_qr
from app.services.export import round_chf
from app.services.rechnung_pdf import invoice_pdf

DATEINAME = "Beispiel-Rechnung.pdf"

#: SIX's documented example QR-IBAN. Deliberately not a real account: the sample
#: is scannable on purpose, and somebody will scan it with a banking app.
BEISPIEL_IBAN = "CH4431999123000889012"

LIEFERANT = swiss_qr.Party(
    name="Muster Büroservice AG",
    strasse="Bahnhofstrasse",
    hausnummer="12",
    plz="8001",
    ort="Zürich",
)
KUNDE = swiss_qr.Party(
    name="Ihre Firma",
    strasse="Beispielweg",
    hausnummer="3",
    plz="6000",
    ort="Luzern",
)

POSITIONEN = [
    ("Büromaterial, Sammelposten", 1.0, "Pauschale", 84.20),
    ("Druckerpatronen schwarz", 2.0, "Stk", 46.50),
    ("Papier A4, 5 Pack", 1.0, "Pack", 38.90),
]
MWST_SATZ = 8.1
ZAHLUNGSFRIST_TAGE = 30
#: Across every page. The sample is a complete, scannable invoice — which is the
#: point and also the risk, so it has to be unmistakable on paper too.
WASSERZEICHEN = "Beispiel"
HINWEIS = (
    "Beispielrechnung zum Ausprobieren — keine echte Forderung, die IBAN ist das Beispiel aus der SIX-Dokumentation."
)


def _netto() -> float:
    return float(round_chf(sum(menge * preis for _, menge, _, preis in POSITIONEN)))


def betraege() -> tuple[float, float, float]:
    """(netto, mwst, brutto) — the same order the invoice prints them."""
    netto = _netto()
    mwst = float(round_chf(netto * MWST_SATZ / 100.0))
    return netto, mwst, float(round_chf(netto + mwst))


def beispiel_pdf(heute: date | None = None) -> bytes:
    """A complete QR-Rechnung a scanner can read, from data that is not real."""
    tag = heute or date.today()
    netto, mwst, brutto = betraege()
    reference = swiss_qr.qrr_reference(1, 1)

    profile = CompanyProfile(
        name=LIEFERANT.name,
        strasse=LIEFERANT.strasse,
        hausnummer=LIEFERANT.hausnummer,
        plz=LIEFERANT.plz,
        ort=LIEFERANT.ort,
        land=LIEFERANT.land,
        iban=BEISPIEL_IBAN,
        email="rechnung@example.ch",
        mwst_nr="CHE-123.456.789 MWST",
        zahlungsfrist_tage=ZAHLUNGSFRIST_TAGE,
        mwst_pct=f"-{MWST_SATZ:.2f}",
    )
    document = Document(
        kind=KIND_RECHNUNG,
        direction=DIRECTION_EINGANG,
        file_key="",
        vendor=LIEFERANT.name,
        amount=brutto,
        currency="CHF",
        invoice_no="2026-0042",
        invoice_date=tag,
        due_date=tag + timedelta(days=ZAHLUNGSFRIST_TAGE),
        qr_iban=BEISPIEL_IBAN,
        qr_reference=reference,
    )
    positions = [
        InvoicePosition(position=index, bezeichnung=text, menge=menge, einheit=einheit, einzelpreis=preis)
        for index, (text, menge, einheit, preis) in enumerate(POSITIONEN, start=1)
    ]
    payload = swiss_qr.build_payload(
        iban=BEISPIEL_IBAN,
        creditor=LIEFERANT,
        amount=brutto,
        reference_type=swiss_qr.REFERENCE_QRR,
        reference=reference,
        message=HINWEIS[: swiss_qr.MESSAGE_MAX],
        debtor=KUNDE,
    )
    return invoice_pdf(
        document,
        positions,
        profile,
        payload,
        kunde=KUNDE,
        reference=reference,
        netto=netto,
        mwst=mwst,
        watermark=WASSERZEICHEN,
    )
