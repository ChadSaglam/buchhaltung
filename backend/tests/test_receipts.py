"""B-09 — uploaded receipts / statement PDFs are persisted through the storage backend.

The key (`receipts/<tenant_id>/<uuid>.<ext>`) is returned by the extraction
endpoints, accepted on booking create only for the caller's own tenant, and
streamed back by GET /api/bookings/{id}/source.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.models.booking import Booking
from app.schemas.scanner import ScannerStatusResponse
from app.services.receipts import (
    content_type_for_key,
    key_belongs_to_tenant,
    read_receipt,
    receipt_key,
    store_receipt,
)
from app.services.scanner.base import ProviderExtractionResult
from app.services.scanner.scanner_service import ScannerService
from app.services.storage import get_storage
from tests.factories import auth_headers, create_booking, create_tenant, create_user

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"


# ── key helpers ──────────────────────────────────────────────────────────────


def test_receipt_key_layout_and_extension():
    key = receipt_key(7, "Rechnung.PDF", "application/pdf")
    assert key.startswith("receipts/7/") and key.endswith(".pdf")
    assert key_belongs_to_tenant(key, 7)
    assert not key_belongs_to_tenant(key, 8)

    # Extension falls back to the content type, then to "bin"; never trusts junk.
    assert receipt_key(7, "photo", "image/jpeg").endswith(".jpg")
    assert receipt_key(7, "../../etc/passwd", "text/plain").endswith(".bin")
    assert receipt_key(7, "x.tar.gz", "").endswith(".gz")


def test_key_belongs_to_tenant_rejects_foreign_or_malformed_keys():
    assert not key_belongs_to_tenant(None, 1)
    assert not key_belongs_to_tenant("", 1)
    assert not key_belongs_to_tenant("models/1/model.pkl", 1)
    assert not key_belongs_to_tenant("receipts/1/../2/" + "a" * 32 + ".pdf", 1)
    assert not key_belongs_to_tenant("receipts/12/" + "a" * 32 + ".pdf", 1)
    assert key_belongs_to_tenant("receipts/1/" + "a" * 32 + ".pdf", 1)


def test_content_type_for_key():
    assert content_type_for_key("receipts/1/x.pdf") == "application/pdf"
    assert content_type_for_key("receipts/1/x.jpg") == "image/jpeg"
    assert content_type_for_key("receipts/1/x.bin") == "application/octet-stream"


def test_store_and_read_receipt_round_trip(storage_dir):
    key = store_receipt(3, filename="beleg.png", content_type="image/png", content=PNG_BYTES)
    assert (storage_dir / key).is_file()
    assert read_receipt(key, 3) == PNG_BYTES
    assert read_receipt(key, 4) is None  # same key, other tenant
    get_storage().delete(key)
    assert read_receipt(key, 3) is None  # file gone


# ── extraction endpoints persist before they parse ───────────────────────────


async def test_scanner_extract_persists_upload_before_extraction(db_session, storage_dir):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    service = ScannerService(db_session, user)
    ocr_result = ProviderExtractionResult(
        data={"ocr_text": "Acme AG Rechnung CHF 100.00"},
        steps=[],
        attempts=[],
        providers=[],
        ocr_provider="custom-ocr",
        ocr_worked=True,
    )
    status = ScannerStatusResponse(
        ok=True,
        error=None,
        models=[],
        vision_models=[],
        best_vision="",
        scanner_mode="custom-first",
        pipeline=[],
        custom_ocr_available=True,
    )
    with (
        patch.object(service.registry, "get_ocr_provider") as mock_ocr,
        patch.object(service.registry, "get_vision_provider") as mock_vision,
        patch(
            "app.services.scanner.scanner_service.parse_invoice_text",
            return_value={"vendor": "Acme AG", "total_amount": 100.0, "vat_rate": 8.1},
        ),
        patch.object(ScannerService, "get_status", new=AsyncMock(return_value=status)),
    ):
        mock_ocr.return_value.is_available.return_value = True
        mock_ocr.return_value.extract_async = AsyncMock(return_value=ocr_result)
        mock_vision.return_value.is_available.return_value = False
        response = await service.extract(file_name="invoice.png", content_type="image/png", content=PNG_BYTES)

    key = response.data.source_key
    assert key and key_belongs_to_tenant(key, tenant.id) and key.endswith(".png")
    assert (storage_dir / key).read_bytes() == PNG_BYTES


async def test_pdf_parse_persists_statement_and_returns_key(client, db_session, storage_dir):
    tenant = await create_tenant(db_session)
    headers = auth_headers(await create_user(db_session, tenant))
    files = {"file": ("auszug.pdf", PDF_BYTES, "application/pdf")}

    with patch("app.routers.pdf.extract_transactions_from_pdf", return_value=[{"Beschreibung": "Miete"}]):
        resp = await client.post("/api/pdf/parse", files=files, headers=headers)

    assert resp.status_code == 200, resp.text
    key = resp.json()["source_key"]
    assert key_belongs_to_tenant(key, tenant.id) and key.endswith(".pdf")
    assert (storage_dir / key).read_bytes() == PDF_BYTES


async def test_pdf_parse_keeps_the_file_when_parsing_fails(client, db_session, storage_dir):
    tenant = await create_tenant(db_session)
    headers = auth_headers(await create_user(db_session, tenant))
    files = {"file": ("kaputt.pdf", PDF_BYTES, "application/pdf")}

    with patch("app.routers.pdf.extract_transactions_from_pdf", side_effect=ValueError("boom")):
        resp = await client.post("/api/pdf/parse", files=files, headers=headers)

    assert resp.status_code == 422
    stored = list((storage_dir / "receipts" / str(tenant.id)).iterdir())
    assert len(stored) == 1 and stored[0].read_bytes() == PDF_BYTES


# ── bookings carry the key and stream the document ───────────────────────────


async def test_booking_create_stores_key_and_source_streams_it(client, db_session, storage_dir):
    tenant = await create_tenant(db_session)
    headers = auth_headers(await create_user(db_session, tenant))
    key = store_receipt(tenant.id, filename="beleg.pdf", content_type="application/pdf", content=PDF_BYTES)

    resp = await client.post(
        "/api/bookings/",
        json=[{"beschreibung": "Miete", "betrag": 1200.0, "source": "kontoauszug", "source_key": key}],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    booking_id = resp.json()[0]["id"]
    await db_session.commit()

    listed = await client.get("/api/bookings/", headers=headers)
    assert listed.json()[0]["source_key"] == key

    src = await client.get(f"/api/bookings/{booking_id}/source", headers=headers)
    assert src.status_code == 200
    assert src.headers["content-type"].startswith("application/pdf")
    assert src.content == PDF_BYTES
    assert "inline" in src.headers["content-disposition"]


async def test_booking_create_rejects_a_key_of_another_tenant(client, db_session):
    tenant = await create_tenant(db_session)
    other = await create_tenant(db_session)
    headers = auth_headers(await create_user(db_session, tenant))
    foreign = store_receipt(other.id, filename="b.pdf", content_type="application/pdf", content=PDF_BYTES)

    for bad in (foreign, "models/1/model.pkl", "receipts/../x.pdf"):
        resp = await client.post("/api/bookings/", json=[{"beschreibung": "x", "source_key": bad}], headers=headers)
        assert resp.status_code == 400, bad
        assert resp.json()["error"]["code"]
    assert (await db_session.execute(Booking.__table__.select())).all() == []


async def test_booking_source_404_without_key_or_missing_file(client, db_session):
    tenant = await create_tenant(db_session)
    headers = auth_headers(await create_user(db_session, tenant))

    manual = await create_booking(db_session, tenant, beschreibung="manuell")
    resp = await client.get(f"/api/bookings/{manual.id}/source", headers=headers)
    assert resp.status_code == 404

    key = store_receipt(tenant.id, filename="b.pdf", content_type="application/pdf", content=PDF_BYTES)
    booking = await create_booking(db_session, tenant, beschreibung="mit Beleg")
    booking.source_key = key
    await db_session.commit()
    get_storage().delete(key)
    resp = await client.get(f"/api/bookings/{booking.id}/source", headers=headers)
    assert resp.status_code == 404

    resp = await client.get("/api/bookings/999999/source", headers=headers)
    assert resp.status_code == 404
