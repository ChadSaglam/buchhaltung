"""B-20 — the sample invoice, and why it has to be a real one.

The point of the sample is that it goes through the *actual* pipeline: if the
product's own QR reader cannot decode it, the first run shows a new user the
fallback path (vision/OCR) and teaches them the wrong thing about what this
product does. So the test that matters decodes it with `qr_bill.read_qr_bill`,
the same function a supplier's invoice goes through.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.onboarding import (
    BEISPIEL_IBAN,
    DATEINAME,
    WASSERZEICHEN,
    ZAHLUNGSFRIST_TAGE,
    beispiel_pdf,
    betraege,
)
from app.services.qr_bill import read_qr_bill
from app.services.swiss_qr import is_qr_iban, is_valid_qrr
from tests.factories import auth_headers, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Neu AG")
    user = await create_user(db_session, tenant, role="viewer")
    return tenant, user, auth_headers(user)


@pytest.fixture(scope="module")
def pdf() -> bytes:
    return beispiel_pdf(date(2026, 9, 16))


def test_the_products_own_reader_decodes_it(pdf):
    bill = read_qr_bill(pdf, "application/pdf")
    assert bill is not None
    assert bill.iban == BEISPIEL_IBAN
    assert bill.amount == pytest.approx(betraege()[2])
    assert bill.reference_type == "QRR"


def test_the_reference_is_a_valid_qrr(pdf):
    # A QR-IBAN *requires* a QRR reference; a sample with a broken one would
    # demonstrate exactly the failure the product exists to avoid.
    assert is_qr_iban(BEISPIEL_IBAN)
    assert is_valid_qrr(read_qr_bill(pdf, "application/pdf").reference)


def test_the_totals_add_up():
    netto, mwst, brutto = betraege()
    assert brutto == pytest.approx(netto + mwst)
    assert mwst == pytest.approx(netto * 8.1 / 100, abs=0.01)


def test_it_is_marked_as_a_sample_on_the_page(pdf):
    # It is a complete, scannable invoice — which is the point and also the risk.
    import re
    import zlib

    streams = re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S)
    text = b""
    for chunk in streams:
        try:
            text += zlib.decompress(chunk.strip(b"\r\n"))
        except Exception:
            text += chunk
    assert WASSERZEICHEN.encode("latin-1") in text


def test_the_due_date_follows_the_invoice_date(pdf):
    assert ZAHLUNGSFRIST_TAGE == 30
    assert b"16.10.2026" in _pdf_text(pdf)


def test_the_qr_message_says_it_is_not_a_real_claim(pdf):
    bill = read_qr_bill(pdf, "application/pdf")
    assert "Beispielrechnung" in bill.message


def test_the_same_day_gives_the_same_file():
    # No randomness, no clock inside the render: a sample that differs run to run
    # would make every diff of a stored copy noise.
    assert beispiel_pdf(date(2026, 9, 16)) == beispiel_pdf(date(2026, 9, 16))


def _pdf_text(pdf: bytes) -> bytes:
    import re
    import zlib

    out = b""
    for chunk in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            out += zlib.decompress(chunk.strip(b"\r\n"))
        except Exception:
            out += chunk
    return out


async def test_the_route_serves_it_as_a_download(client, actor):
    _t, _u, headers = actor
    res = await client.get("/api/onboarding/beispiel-rechnung.pdf", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert DATEINAME in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF-")


async def test_a_viewer_may_fetch_it(client, actor):
    # Trying the product out is not a write.
    _t, _u, headers = actor
    assert (await client.get("/api/onboarding/beispiel-rechnung.pdf", headers=headers)).status_code == 200


async def test_it_still_needs_a_token(client):
    # B-55 narrowed the unauthenticated surface on purpose; a first-run helper
    # is not a reason to widen it again.
    assert (await client.get("/api/onboarding/beispiel-rechnung.pdf")).status_code in (401, 403)
