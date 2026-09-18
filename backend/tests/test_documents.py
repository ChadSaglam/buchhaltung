"""Documents (phase 1): bulk upload, QR-bill first, list/summary/patch/file, isolation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.models.document import Document
from app.schemas.scanner import ExtractedInvoice, ScannerExtractResponse
from app.services.scanner.scanner_service import ScannerService
from tests.factories import auth_headers, create_tenant, create_user
from tests.test_qr_bill import QRR, png_with_qr, spc

PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6364f8cfc000000301"
    "0100c9fe92ef0000000049454e44ae426082"
)


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


def _files(*items):
    return [("files", (name, content, ctype)) for name, content, ctype in items]


@pytest.mark.asyncio
async def test_qr_bill_wins_and_scanner_is_not_called(client, actor):
    _tenant, _user, headers = actor
    with patch.object(ScannerService, "extract", new=AsyncMock(side_effect=AssertionError("scanner used"))):
        resp = await client.post(
            "/api/documents/", files=_files(("cembra.png", png_with_qr(spc()), "image/png")), headers=headers
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["created"], body["failed"]) == (1, 0)
    doc = body["results"][0]["document"]
    assert doc["status"] == "offen"
    assert doc["vendor"] == "Cembra Money Bank AG"
    assert doc["amount"] == 1949.45
    assert (doc["qr_reference"], doc["qr_iban"]) == (QRR, "CH4431999123000889012")
    assert doc["invoice_no"] == "2026-0042"
    assert doc["extraction_source"] == "qr"
    # B-92: "Cembra Money Bank AG" matches no keyword and this tenant has no model
    # yet, so the classifier proposes nothing rather than a 6500 that would have
    # been just as wrong (Cembra is 6260 in the owner's own ledger). The Beleg is
    # created either way — the account is a field the user fills or the memory
    # learns on the first correction.
    assert doc["kt_soll"] == ""
    assert doc["classification_confidence"] == 0.0


@pytest.mark.asyncio
async def test_bulk_upload_mixes_success_scanner_fallback_and_failure(client, actor):
    _tenant, _user, headers = actor
    scanned = ScannerExtractResponse(
        data=ExtractedInvoice(
            vendor="Agrola AG", total_amount=153.05, date="12.04.2026", invoice_number="R-9", vat_rate=8.1
        )
    )
    with patch.object(ScannerService, "extract", new=AsyncMock(return_value=scanned)):
        resp = await client.post(
            "/api/documents/",
            files=_files(
                ("qr.png", png_with_qr(spc(amount="87.55")), "image/png"),
                ("tankstelle.png", PNG_1x1, "image/png"),
                ("notes.txt", b"hello", "text/plain"),
            ),
            headers=headers,
        )
    body = resp.json()
    assert (body["created"], body["failed"]) == (2, 1)
    by_name = {r["filename"]: r for r in body["results"]}
    assert by_name["qr.png"]["document"]["extraction_source"] == "qr"
    scanned_doc = by_name["tankstelle.png"]["document"]
    assert (scanned_doc["vendor"], scanned_doc["amount"], scanned_doc["invoice_date"]) == (
        "Agrola AG",
        153.05,
        "2026-04-12",
    )
    assert scanned_doc["extraction_source"] == "vision"
    assert by_name["notes.txt"]["ok"] is False and "Nur Bilder" in by_name["notes.txt"]["error"]


@pytest.mark.asyncio
async def test_scanner_failure_becomes_a_fehler_row_not_a_500(client, actor):
    _tenant, _user, headers = actor
    with patch.object(
        ScannerService, "extract", new=AsyncMock(side_effect=HTTPException(422, "Keine Rechnung erkannt."))
    ):
        resp = await client.post("/api/documents/", files=_files(("blank.png", PNG_1x1, "image/png")), headers=headers)
    body = resp.json()
    assert body["failed"] == 1
    doc = body["results"][0]["document"]
    assert doc["status"] == "fehler" and doc["error"] == "Keine Rechnung erkannt."
    # the file is still stored and viewable
    assert (await client.get(f"/api/documents/{doc['id']}/file", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_list_summary_patch_and_isolation(client, actor, db_session):
    tenant, user, headers = actor
    resp = await client.post(
        "/api/documents/",
        files=_files(
            ("a.png", png_with_qr(spc(amount="100.00")), "image/png"),
            ("b.png", png_with_qr(spc(amount="50.50", ref=QRR)), "image/png"),
        ),
        headers=headers,
    )
    ids = [r["document"]["id"] for r in resp.json()["results"]]

    listed = (await client.get("/api/documents/", headers=headers)).json()
    assert listed["count"] == 2
    summary = (await client.get("/api/documents/summary", headers=headers)).json()
    assert (summary["offen"], summary["offen_betrag"], summary["ueberfaellig"]) == (2, 150.5, 0)

    patched = await client.patch(
        f"/api/documents/{ids[0]}",
        json={"status": "bezahlt", "due_date": "2026-01-01", "vendor": "  Cembra  "},
        headers=headers,
    )
    assert patched.status_code == 200 and patched.json()["status"] == "bezahlt"
    summary = (await client.get("/api/documents/summary", headers=headers)).json()
    assert (summary["offen"], summary["bezahlt"], summary["offen_betrag"]) == (1, 1, 50.5)
    assert (await client.get("/api/documents/?status=bezahlt", headers=headers)).json()["count"] == 1
    assert (await client.get("/api/documents/?status=nope", headers=headers)).status_code == 400

    # exported is final
    await client.patch(f"/api/documents/{ids[1]}", json={"status": "exportiert"}, headers=headers)
    assert (
        await client.patch(f"/api/documents/{ids[1]}", json={"status": "offen"}, headers=headers)
    ).status_code == 409

    # another tenant sees nothing
    other = await create_user(db_session, await create_tenant(db_session))
    oh = auth_headers(other)
    assert (await client.get("/api/documents/", headers=oh)).json()["count"] == 0
    assert (await client.get(f"/api/documents/{ids[0]}", headers=oh)).status_code == 404
    assert (await client.get(f"/api/documents/{ids[0]}/file", headers=oh)).status_code == 404
    assert (await client.patch(f"/api/documents/{ids[0]}", json={"vendor": "x"}, headers=oh)).status_code == 404

    # a viewer may read, not write
    viewer = await create_user(db_session, tenant, role="viewer")
    vh = auth_headers(viewer)
    assert (await client.get("/api/documents/", headers=vh)).status_code == 200
    assert (await client.patch(f"/api/documents/{ids[0]}", json={"vendor": "x"}, headers=vh)).status_code == 403
    assert (
        await client.post("/api/documents/", files=_files(("a.png", PNG_1x1, "image/png")), headers=vh)
    ).status_code == 403

    row = await db_session.get(Document, ids[0])
    assert row is not None and row.uploaded_by == user.id


@pytest.mark.asyncio
async def test_too_many_files(client, actor):
    _tenant, _user, headers = actor
    resp = await client.post(
        "/api/documents/", files=_files(*[(f"{i}.png", PNG_1x1, "image/png") for i in range(51)]), headers=headers
    )
    assert resp.status_code == 400
