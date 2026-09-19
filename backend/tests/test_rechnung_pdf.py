"""B-77/B-79 — die Rechnung als PDF, mit einem Zahlteil, den ein Scanner liest.

Der eine Test, auf den es ankommt, ist `test_the_qr_in_the_pdf_decodes_back…`:
er liest den QR-Code aus dem gerenderten PDF und vergleicht ihn Zeichen für
Zeichen mit dem Payload, den `swiss_qr.build_payload` gebaut hat. Alles andere
ist Layout — das hier ist die Frage, ob eine Bank die Rechnung bezahlen kann.
"""

from __future__ import annotations

import datetime
import io

import pytest

from app.models.company_profile import CompanyProfile
from app.models.document import Document
from app.models.invoice_position import InvoicePosition
from app.services import swiss_qr
from app.services.rechnung_pdf import (
    EMPFANGSSCHEIN_WIDTH,
    PAGE_HEIGHT,
    QR_QUIET,
    QR_SIZE,
    ZAHLTEIL_HEIGHT,
    ZAHLTEIL_TOP,
    invoice_pdf,
)

QR_IBAN = "CH4431999123000889012"
QRR = "210000000003139471430009017"


def _profile(**overrides) -> CompanyProfile:
    return CompanyProfile(
        **{
            "tenant_id": 1,
            "name": "Muster Informatik GmbH",
            "strasse": "Bahnhofstrasse",
            "hausnummer": "12",
            "plz": "8001",
            "ort": "Zürich",
            "land": "CH",
            "iban": QR_IBAN,
            "mwst_nr": "CHE-123.456.789 MWST",
            "email": "rechnung@muster.ch",
            "telefon": "044 123 45 67",
            "mwst_pct": "-8.10",
            **overrides,
        }
    )


def _kunde() -> swiss_qr.Party:
    return swiss_qr.Party(name="Beispiel AG", strasse="Musterweg", hausnummer="5", plz="3000", ort="Bern", land="CH")


def _document(**overrides) -> Document:
    return Document(
        **{
            "id": 7,
            "tenant_id": 1,
            "direction": "ausgang",
            "file_key": "receipts/1/x.pdf",
            "filename": "x.pdf",
            "vendor": "Beispiel AG",
            "amount": 691.84,
            "currency": "CHF",
            "invoice_no": "2026-0001",
            "invoice_date": datetime.date(2026, 9, 16),
            "due_date": datetime.date(2026, 10, 16),
            "qr_reference": QRR,
            "qr_message": "",
            **overrides,
        }
    )


def _payload(profile: CompanyProfile, doc: Document, kunde: swiss_qr.Party) -> str:
    return swiss_qr.build_payload(
        iban=profile.iban,
        creditor=swiss_qr.Party(
            name=profile.name,
            strasse=profile.strasse,
            hausnummer=profile.hausnummer,
            plz=profile.plz,
            ort=profile.ort,
        ),
        amount=doc.amount,
        currency=doc.currency,
        reference_type=swiss_qr.REFERENCE_QRR,
        reference=doc.qr_reference,
        message="",
        debtor=kunde,
    )


def _render(**doc_overrides) -> tuple[bytes, str]:
    profile = _profile()
    doc = _document(**doc_overrides)
    kunde = _kunde()
    payload = _payload(profile, doc, kunde)
    positions = [
        InvoicePosition(position=1, bezeichnung="Beratung und Konzept", menge=4, einheit="Std", einzelpreis=150.0),
        InvoicePosition(position=2, bezeichnung="Spesen", menge=1, einheit="", einzelpreis=40.0),
    ]
    content = invoice_pdf(
        doc,
        positions,
        profile,
        payload,
        kunde=kunde,
        reference=swiss_qr.format_reference(doc.qr_reference, swiss_qr.REFERENCE_QRR),
        netto=640.0,
        mwst=51.84,
    )
    return content, payload


# --- Das PDF selbst ---------------------------------------------------------


def test_it_is_a_pdf_and_it_is_one_page():
    content, _payload = _render()
    assert content.startswith(b"%PDF-")
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        assert len(pdf.pages) == 1


def test_the_letter_carries_what_the_customer_needs_to_pay():
    content, _payload = _render()
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text = pdf.pages[0].extract_text()

    for expected in (
        "Rechnung 2026-0001",
        "Muster Informatik GmbH",
        "Beispiel AG",
        "Beratung und Konzept",
        "691.84",
        "16.10.2026",
        "Empfangsschein",
        "Zahlteil",
        "21 00000 00003 13947 14300 09017",
    ):
        assert expected in text, expected


def test_no_page_number_lands_inside_the_payment_part():
    """The Zahlteil is a fixed SIX template — nothing of ours may sit in it."""
    content, _payload = _render()
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        assert "Seite" not in pdf.pages[0].extract_text()


def test_the_payment_part_sits_where_the_template_says():
    """105 mm tall, 62 mm receipt — the numbers a bank's slitter relies on."""
    assert ZAHLTEIL_HEIGHT == 105.0
    assert EMPFANGSSCHEIN_WIDTH == 62.0
    assert ZAHLTEIL_TOP == PAGE_HEIGHT - ZAHLTEIL_HEIGHT
    assert QR_SIZE == 46.0
    assert QR_QUIET == 5.0


def test_the_page_is_a4():
    content, _payload = _render()
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        page = pdf.pages[0]
    # A4 in PostScript points, within a rounding of a millimetre.
    assert abs(float(page.width) - 595.28) < 3
    assert abs(float(page.height) - 841.89) < 3


# --- Der Teil, der zählt ----------------------------------------------------


def test_the_qr_in_the_pdf_decodes_back_to_the_payload_we_built():
    """A QR-bill a scanner cannot read is worse than no QR at all.

    Rendered at 6x and decoded, so this fails if the module grid is off by a
    fraction, if the Swiss cross covers a data module, or if the quiet zone
    disappears — none of which a byte-comparison of the PDF would catch.
    """
    pdfium = pytest.importorskip("pypdfium2")
    zxingcpp = pytest.importorskip("zxingcpp")

    content, payload = _render()
    image = pdfium.PdfDocument(io.BytesIO(content))[0].render(scale=6).to_pil()
    found = zxingcpp.read_barcodes(image)

    assert len(found) == 1, "exactly one barcode belongs on an invoice"
    assert found[0].valid
    assert found[0].text == payload
    assert len(found[0].text.split("\n")) == 31  # Swiss Payments Code


def test_the_decoded_payload_still_carries_the_reference_the_abgleich_matches_on():
    """The reference is what books the payment later (B-68) — it must survive the round trip."""
    pdfium = pytest.importorskip("pypdfium2")
    zxingcpp = pytest.importorskip("zxingcpp")

    content, _payload = _render()
    image = pdfium.PdfDocument(io.BytesIO(content))[0].render(scale=6).to_pil()
    decoded = zxingcpp.read_barcodes(image)[0].text.split("\n")

    assert decoded[decoded.index(swiss_qr.REFERENCE_QRR) + 1] == QRR
    assert "691.84" in decoded


# --- Randfälle --------------------------------------------------------------


def test_an_invoice_without_a_reference_still_renders():
    content, _payload = _render(qr_reference="", raw_json='{"referenz_typ": "NON"}')
    assert content.startswith(b"%PDF-")
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text = pdf.pages[0].extract_text()
    assert "Referenz" not in text
    assert "Zahlteil" in text


def test_typographic_characters_do_not_kill_the_renderer():
    """fpdf2's core fonts are latin-1; „Anführungszeichen" and – dashes must not raise."""
    profile = _profile(name="Müller & Co. – „Beste Qualität“")
    doc = _document(qr_message="Auftrag – Nr. 12 „dringend“")
    kunde = _kunde()
    positions = [
        InvoicePosition(position=1, bezeichnung="Beratung – „Paket A“", menge=1, einheit="", einzelpreis=100.0)
    ]
    content = invoice_pdf(
        doc,
        positions,
        profile,
        _payload(profile, doc, kunde),
        kunde=kunde,
        reference=swiss_qr.format_reference(QRR, swiss_qr.REFERENCE_QRR),
        netto=100.0,
        mwst=8.1,
    )
    assert content.startswith(b"%PDF-")


def test_a_customer_with_no_address_gets_a_readable_line_not_a_crash():
    profile = _profile()
    doc = _document()
    kunde = swiss_qr.Party(name="Beispiel AG")
    content = invoice_pdf(
        doc,
        [InvoicePosition(position=1, bezeichnung="X", menge=1, einheit="", einzelpreis=1.0)],
        profile,
        _payload(profile, doc, kunde),
        kunde=kunde,
        reference="",
        netto=1.0,
        mwst=0.0,
    )
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        assert "Beispiel AG" in pdf.pages[0].extract_text()


def test_the_file_name_is_the_invoice_number():
    from app.services.rechnung import RechnungService

    service = RechnungService.__new__(RechnungService)
    assert service.dateiname(_document()) == "Rechnung-2026-0001.pdf"
    assert service.dateiname(_document(invoice_no="", id=42)) == "Rechnung-42.pdf"
    assert service.dateiname(_document(invoice_no="2026/07 A")) == "Rechnung-2026-07-A.pdf"
