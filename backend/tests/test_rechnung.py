"""Rechnungen schreiben mit Swiss QR (B-68).

Three things have to be true, and each is tested on its own:
1. the reference rules (QR-IBAN → QRR, normal IBAN → SCOR, check digits),
2. the payload the customer's banking app scans round-trips through our own reader,
3. writing an invoice produces the Debitorenbuchung and an open item whose
   reference the Abgleich later recognises on the bank statement.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.models.bank_transaction import BankTransaction
from app.models.booking import Booking
from app.models.company_profile import CompanyProfile
from app.models.document import DIRECTION_AUSGANG, STATUS_BEZAHLT, STATUS_OFFEN, Document
from app.models.invoice_position import InvoicePosition
from app.services import swiss_qr
from app.services.abgleich import AbgleichService
from app.services.qr_bill import parse_swiss_qr
from app.services.rechnung import PositionInput, totals_for
from tests.factories import auth_headers, create_tenant, create_user

# SIX documentation examples.
QR_IBAN = "CH4431999123000889012"
NORMAL_IBAN = "CH9300762011623852957"


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Chadev GmbH")
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


async def _profile(db_session, tenant, **overrides) -> CompanyProfile:
    profile = CompanyProfile(
        tenant_id=tenant.id,
        name="Chadev GmbH",
        strasse="Bahnhofstrasse",
        hausnummer="1",
        plz="8001",
        ort="Zürich",
        **{"iban": QR_IBAN, **overrides},
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


RECHNUNG = {
    "kunde": {"name": "Muster AG", "strasse": "Seestrasse", "hausnummer": "12", "plz": "6003", "ort": "Luzern"},
    "positionen": [
        {"bezeichnung": "Beratung", "menge": 4, "einheit": "h", "einzelpreis": 150.0},
        {"bezeichnung": "Spesen", "menge": 1, "einzelpreis": 40.0},
    ],
}


# ── die reinen Regeln ────────────────────────────────────────────────────────


def test_iban_validation_and_qr_iban_detection():
    assert swiss_qr.is_valid_iban(QR_IBAN) and swiss_qr.is_qr_iban(QR_IBAN)
    assert swiss_qr.is_valid_iban(NORMAL_IBAN) and not swiss_qr.is_qr_iban(NORMAL_IBAN)
    assert not swiss_qr.is_valid_iban("CH4431999123000889013")  # broken check digit
    assert not swiss_qr.is_valid_iban("DE89370400440532013000")  # not CH/LI
    assert swiss_qr.format_iban(QR_IBAN) == "CH44 3199 9123 0008 8901 2"


def test_qrr_reference_is_27_digits_with_a_valid_check_digit():
    reference = swiss_qr.qrr_reference(7, 42)
    assert len(reference) == 27 and reference.isdigit()
    assert swiss_qr.is_valid_qrr(reference)
    assert not swiss_qr.is_valid_qrr(reference[:-1] + str((int(reference[-1]) + 1) % 10))
    assert swiss_qr.qrr_reference(7, 42) != swiss_qr.qrr_reference(7, 43)
    assert swiss_qr.qrr_reference(7, 42) != swiss_qr.qrr_reference(8, 42)


def test_scor_reference_follows_iso_11649():
    reference = swiss_qr.scor_reference("2026-0042")
    assert reference.startswith("RF") and swiss_qr.is_valid_scor(reference)
    assert swiss_qr.is_valid_scor("RF18539007547034")  # ISO example
    assert not swiss_qr.is_valid_scor("RF19539007547034")


def test_reference_type_follows_the_iban():
    assert swiss_qr.reference_for(QR_IBAN, tenant_id=1, document_id=1, invoice_no="2026-0001")[0] == "QRR"
    assert swiss_qr.reference_for(NORMAL_IBAN, tenant_id=1, document_id=1, invoice_no="2026-0001")[0] == "SCOR"
    assert swiss_qr.reference_for("", tenant_id=1, document_id=1, invoice_no="2026-0001") == ("NON", "")


def test_reference_formatting():
    assert swiss_qr.format_reference("210000000003139471430009017", "QRR") == "21 00000 00003 13947 14300 09017"
    assert swiss_qr.format_reference("RF18539007547034", "SCOR") == "RF18 5390 0754 7034"


def test_totals_add_vat_on_top_of_net_prices():
    positions = [PositionInput("Beratung", 4, "h", 150.0), PositionInput("Spesen", 1, "", 40.0)]
    totals = totals_for(positions, "-8.10")
    assert totals.netto == 640.0
    assert totals.brutto == 691.84  # 640 * 1.081
    assert round(totals.netto + totals.mwst, 2) == totals.brutto
    assert totals_for(positions, "").brutto == 640.0  # not VAT registered


def test_payload_round_trips_through_our_own_reader():
    """What the customer's banking app scans must parse as a Swiss QR-bill."""
    reference = swiss_qr.qrr_reference(7, 42)
    payload = swiss_qr.build_payload(
        iban=QR_IBAN,
        creditor=swiss_qr.Party(name="Chadev GmbH", strasse="Bahnhofstrasse", hausnummer="1", plz="8001", ort="Zürich"),
        amount=691.84,
        reference_type="QRR",
        reference=reference,
        debtor=swiss_qr.Party(name="Muster AG", strasse="Seestrasse", hausnummer="12", plz="6003", ort="Luzern"),
    )
    assert len(payload.split("\n")) == 31
    bill = parse_swiss_qr(payload)
    assert bill is not None
    assert bill.iban == QR_IBAN
    assert bill.creditor_name == "Chadev GmbH"
    assert bill.amount == 691.84
    assert (bill.reference_type, bill.reference) == ("QRR", reference)
    assert bill.debtor_name == "Muster AG"


def test_qr_svg_is_vector_and_carries_the_swiss_cross():
    svg = swiss_qr.qr_svg(swiss_qr.build_payload(iban=QR_IBAN, creditor=swiss_qr.Party(name="X"), amount=10.0))
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'width="46.0mm"' in svg
    assert svg.count("<rect") >= 5  # background + cross (white, black, two bars)


# ── die Rechnung ─────────────────────────────────────────────────────────────


async def test_profile_starts_empty_and_says_what_is_missing(client, db_session, actor):
    _tenant, _user, headers = actor
    response = await client.get("/api/rechnungen/firma", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["bereit"] is False and "IBAN" in body["fehlt"]
    assert body["konto_debitoren"] == "1100" and body["mwst_code"] == "V81"

    saved = await client.put(
        "/api/rechnungen/firma",
        headers=headers,
        json={"name": "Chadev GmbH", "iban": "CH44 3199 9123 0008 8901 2", "plz": "8001", "ort": "Zürich"},
    )
    assert saved.status_code == 200
    assert saved.json()["bereit"] is True
    assert saved.json()["qr_iban"] is True
    assert saved.json()["referenz_typ"] == "QRR"
    assert saved.json()["iban_formatiert"] == "CH44 3199 9123 0008 8901 2"


async def test_a_broken_iban_is_refused(client, actor):
    _tenant, _user, headers = actor
    response = await client.put("/api/rechnungen/firma", headers=headers, json={"iban": "CH4431999123000889013"})
    assert response.status_code == 400


async def test_writing_an_invoice_without_a_profile_is_refused(client, actor):
    _tenant, _user, headers = actor
    response = await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)
    assert response.status_code == 409
    assert "Firmenprofil" in response.json()["error"]["message"]


async def test_writing_an_invoice_creates_the_debitorenbuchung_and_an_open_item(client, db_session, actor):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)

    response = await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)
    assert response.status_code == 201
    body = response.json()

    assert body["netto"] == 640.0 and body["total"] == 691.84
    assert body["referenz_typ"] == "QRR"
    assert body["document"]["invoice_no"] == f"{date.today().year}-0001"
    assert body["document"]["direction"] == DIRECTION_AUSGANG
    assert body["document"]["status"] == STATUS_OFFEN
    assert swiss_qr.is_valid_qrr(body["document"]["qr_reference"])
    assert len(body["positionen"]) == 2 and body["positionen"][0]["betrag"] == 600.0

    booking = (await db_session.execute(select(Booking).where(Booking.tenant_id == tenant.id))).scalar_one()
    assert (booking.kt_soll, booking.kt_haben) == ("1100", "3000")
    assert booking.betrag == 691.84
    assert booking.mwst_code == "V81" and booking.mwst_amount == 51.84
    assert booking.rechnung == body["document"]["invoice_no"]

    # The payment leg is what the Abgleich will book when the money arrives.
    doc = (await db_session.execute(select(Document).where(Document.tenant_id == tenant.id))).scalar_one()
    assert (doc.kt_soll, doc.kt_haben) == ("1020", "1100")
    assert doc.mwst_code == ""  # the VAT is on the invoice booking, never twice

    positions = (
        (await db_session.execute(select(InvoicePosition).where(InvoicePosition.tenant_id == tenant.id)))
        .scalars()
        .all()
    )
    assert [p.position for p in positions] == [1, 2]


async def test_invoice_numbers_run_continuously(client, db_session, actor):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    first = await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)
    second = await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)
    year = date.today().year
    assert first.json()["document"]["invoice_no"] == f"{year}-0001"
    assert second.json()["document"]["invoice_no"] == f"{year}-0002"

    listing = await client.get("/api/rechnungen/", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["count"] == 2
    assert listing.json()["naechste_nummer"] == f"{year}-0003"


async def test_an_invoice_without_positions_is_refused(client, db_session, actor):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    response = await client.post(
        "/api/rechnungen/", headers=headers, json={"kunde": {"name": "Muster AG"}, "positionen": []}
    )
    assert response.status_code == 422


async def test_the_print_view_contains_the_qr_and_the_total(client, db_session, actor):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    created = await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)
    document_id = created.json()["document"]["id"]

    page = await client.get(f"/api/rechnungen/{document_id}/rechnung.html", headers=headers)
    assert page.status_code == 200
    html = page.text
    assert "<svg" in html and "Zahlteil" in html and "Empfangsschein" in html
    assert "691.84" in html
    assert "Muster AG" in html and "CH44 3199 9123 0008 8901 2" in html
    assert created.json()["referenz_formatiert"] in html


async def test_a_normal_iban_gets_a_scor_reference(client, db_session, actor):
    tenant, _user, headers = actor
    await _profile(db_session, tenant, iban=NORMAL_IBAN)
    body = (await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)).json()
    assert body["referenz_typ"] == "SCOR"
    assert swiss_qr.is_valid_scor(body["document"]["qr_reference"])


async def test_the_payment_closes_the_loop_through_the_abgleich(client, db_session, actor):
    """The reference comes back on the statement → Abgleich books 1020/1100, invoice paid."""
    tenant, user, headers = actor
    await _profile(db_session, tenant)
    created = (await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)).json()
    reference = created["document"]["qr_reference"]

    db_session.add(
        BankTransaction(
            tenant_id=tenant.id,
            value_date=date.today(),
            description="Gutschrift Muster AG",
            amount=691.84,
            reference=reference,
            counterparty="Muster AG",
        )
    )
    await db_session.commit()

    service = AbgleichService(db_session, user)
    proposals = await service.refresh_proposals()
    assert len(proposals) == 1 and proposals[0].tier == "referenz"

    bookings = await service.confirm(proposals[0].transaction_id)
    await db_session.commit()
    assert len(bookings) == 1
    assert (bookings[0].kt_soll, bookings[0].kt_haben) == ("1020", "1100")
    assert bookings[0].mwst_amount == 0.0  # VAT was already booked with the invoice

    doc = (await db_session.execute(select(Document).where(Document.id == created["document"]["id"]))).scalar_one()
    assert doc.status == STATUS_BEZAHLT


async def test_another_tenant_can_neither_read_nor_print_the_invoice(client, db_session, actor):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    created = (await client.post("/api/rechnungen/", headers=headers, json=RECHNUNG)).json()
    document_id = created["document"]["id"]

    other_tenant = await create_tenant(db_session, name="Fremde AG")
    other_user = await create_user(db_session, other_tenant, role="owner")
    other = auth_headers(other_user)

    assert (await client.get(f"/api/rechnungen/{document_id}", headers=other)).status_code == 404
    assert (await client.get(f"/api/rechnungen/{document_id}/rechnung.html", headers=other)).status_code == 404
    assert (await client.get("/api/rechnungen/", headers=other)).json()["count"] == 0

    profile = await client.get("/api/rechnungen/firma", headers=other)
    assert profile.json()["iban"] == ""  # a fresh, empty profile — never the neighbour's


async def test_a_viewer_may_read_but_not_write(client, db_session, actor):
    tenant, _user, _headers = actor
    await _profile(db_session, tenant)
    viewer = await create_user(db_session, tenant, role="viewer")
    viewer_headers = auth_headers(viewer)

    assert (await client.get("/api/rechnungen/firma", headers=viewer_headers)).status_code == 200
    assert (await client.post("/api/rechnungen/", headers=viewer_headers, json=RECHNUNG)).status_code == 403
    assert (await client.put("/api/rechnungen/firma", headers=viewer_headers, json={"name": "X"})).status_code == 403
