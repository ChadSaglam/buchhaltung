"""Swiss QR-bill decoding — phase 1 of the brainstorm. Exact facts beat OCR guesses."""

from __future__ import annotations

import io

import pytest

from app.services.qr_bill import (
    decode_qr_payloads,
    invoice_number_from_message,
    parse_swiss_qr,
    read_qr_bill,
)

# 27-digit QRR reference with a valid mod-10 check digit.
QRR = "210000000003139471430009017"


def spc(amount="1949.45", ref_type="QRR", ref=QRR, message="Rechnung 2026-0042", currency="CHF") -> str:
    return "\n".join(
        [
            "SPC", "0200", "1",
            "CH4431999123000889012",
            "S", "Cembra Money Bank AG", "Bändliweg", "21", "8048", "Zürich", "CH",
            "", "", "", "", "", "", "",
            amount, currency,
            "S", "RDS Isolierungen GmbH", "Industriestrasse", "5", "8307", "Effretikon", "CH",
            ref_type, ref, message, "EPD",
        ]
    )  # fmt: skip


def png_with_qr(payload: str) -> bytes:
    import segno

    buf = io.BytesIO()
    segno.make(payload, error="m").save(buf, kind="png", scale=6, border=4)
    return buf.getvalue()


def test_parse_full_payload():
    bill = parse_swiss_qr(spc())
    assert bill is not None
    assert bill.iban == "CH4431999123000889012"
    assert bill.creditor_name == "Cembra Money Bank AG"
    assert bill.amount == 1949.45 and bill.currency == "CHF"
    assert (bill.reference_type, bill.reference) == ("QRR", QRR)
    assert bill.debtor_name == "RDS Isolierungen GmbH"
    assert bill.creditor_address == "Bändliweg 21 8048 Zürich"


@pytest.mark.parametrize(
    "payload",
    [
        "https://example.com",  # a QR that is not a bill
        spc().replace("SPC", "XYZ", 1),
        spc(ref=QRR[:-1] + "0"),  # broken check digit
        spc().replace("CH4431999123000889012", "DE89370400440532013000"),  # not CH/LI
        spc(ref_type="FOO"),
    ],
)
def test_reject_non_bills(payload):
    assert parse_swiss_qr(payload) is None


def test_non_reference_and_empty_amount():
    bill = parse_swiss_qr(spc(amount="", ref_type="NON", ref=""))
    assert bill is not None
    assert bill.amount is None and bill.reference == "" and bill.reference_type == "NON"


def test_scor_reference_is_kept_verbatim_without_spaces():
    bill = parse_swiss_qr(spc(ref_type="SCOR", ref="RF18 5390 0754 7034"))
    assert bill is not None
    assert bill.reference == "RF18539007547034"


@pytest.mark.parametrize(
    ("message", "number"),
    [
        ("Rechnung 2026-0042", "2026-0042"),
        ("Re-Nr. 4711 vom 3.4.", "4711"),
        ("Invoice #A-12/2026", "A-12/2026"),
        ("Danke für Ihren Einkauf", ""),
    ],
)
def test_invoice_number_from_message(message, number):
    assert invoice_number_from_message(message) == number


def test_decode_from_png_and_read_bill():
    content = png_with_qr(spc())
    assert decode_qr_payloads(content, "image/png") == [spc()]
    bill = read_qr_bill(content, "image/png")
    assert bill is not None and bill.amount == 1949.45


def test_decode_from_pdf():
    from PIL import Image

    png = png_with_qr(spc(amount="87.55"))
    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buf, format="PDF", resolution=200)
    bill = read_qr_bill(buf.getvalue(), "application/pdf")
    assert bill is not None and bill.amount == 87.55


def test_garbage_is_not_an_error():
    assert decode_qr_payloads(b"not an image", "image/png") == []
    assert read_qr_bill(b"%PDF-1.4 broken", "application/pdf") is None
