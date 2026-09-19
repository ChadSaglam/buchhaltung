"""B-17 — the whole hand-off in one file.

The tests that matter are about what the pack *says* rather than what it
contains. A zip with eleven receipts and forty bookings looks complete; the
useful artefact is the one that names the twenty-nine bookings with no receipt,
because that list is the Treuhänder's actual review task and the only thing they
would otherwise have to derive by hand.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from app.models.booking import Booking
from app.models.document import Document
from app.services.export_batch import ExportBatchService
from app.services.storage import get_storage
from app.services.treuhand_pack import (
    BELEGE_DIR,
    BUCHUNGEN_CSV,
    BUCHUNGEN_TSV,
    LIESMICH,
    PROTOKOLL_CSV,
    UEBERSICHT,
    TreuhandPackService,
    beleg_name,
    safe_name,
)
from tests.factories import auth_headers, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


async def add_booking(db, tenant, *, text="Lieferant AG", betrag=100.0, datum="05.04.2026") -> Booking:
    booking = Booking(
        tenant_id=tenant.id,
        datum=datum,
        beschreibung=text,
        betrag=betrag,
        kt_soll="4000",
        kt_haben="1020",
        mwst_code="I81",
        mwst_pct="8.10",
        mwst_amount=7.49,
        source="test",
    )
    db.add(booking)
    await db.flush()
    return booking


async def attach_document(db, tenant, booking, *, filename="rechnung.pdf", vendor="Migros", body=b"%PDF-1.4 x"):
    key = f"tenant-{tenant.id}/{booking.id}-{filename}"
    get_storage().save(key, body, "application/pdf")
    document = Document(
        tenant_id=tenant.id,
        file_key=key,
        filename=filename,
        vendor=vendor,
        booking_id=booking.id,
        amount=float(booking.betrag or 0.0),
    )
    db.add(document)
    await db.flush()
    return document


async def make_pack(db, tenant, user) -> zipfile.ZipFile:
    batch = await ExportBatchService(db, user).create()
    _name, content = await TreuhandPackService(db, user).build(batch.id)
    return zipfile.ZipFile(io.BytesIO(content))


# --- filenames ------------------------------------------------------------


def test_a_vendor_name_cannot_escape_the_archive():
    # Vendor names come out of OCR, so they contain everything.
    assert "/" not in safe_name("../../etc/passwd")
    assert "\\" not in safe_name("C:\\Windows\\System32")
    assert safe_name("Bäckerei Müller & Co.") == "B-ckerei-M-ller-Co"


def test_a_name_that_collapses_to_nothing_gets_a_fallback():
    assert safe_name("///") == "Beleg"
    assert safe_name("", "X") == "X"


def test_the_receipt_is_numbered_after_its_booking():
    doc = Document(vendor="Migros", filename="scan.PDF")
    assert beleg_name(47, doc) == f"{BELEGE_DIR}/047-Migros.pdf"


def test_a_receipt_without_an_extension_keeps_working():
    assert beleg_name(1, Document(vendor="Migros", filename="scan")) == f"{BELEGE_DIR}/001-Migros"


# --- what is in the zip ---------------------------------------------------


async def test_the_pack_holds_every_part_of_the_hand_off(db_session, actor):
    tenant, user, _headers = actor
    booking = await add_booking(db_session, tenant)
    await attach_document(db_session, tenant, booking)
    archive = await make_pack(db_session, tenant, user)
    names = set(archive.namelist())
    assert {LIESMICH, UEBERSICHT, BUCHUNGEN_TSV, BUCHUNGEN_CSV, PROTOKOLL_CSV} <= names
    assert any(n.startswith(f"{BELEGE_DIR}/") for n in names)


async def test_the_import_file_is_the_batch_byte_for_byte(db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant)
    service = ExportBatchService(db_session, user)
    batch = await service.create()
    _batch, expected = await service.content(batch.id)
    _name, content = await TreuhandPackService(db_session, user).build(batch.id)
    assert zipfile.ZipFile(io.BytesIO(content)).read(BUCHUNGEN_TSV).decode() == expected


async def test_the_cover_sheet_is_a_real_pdf(db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant)
    archive = await make_pack(db_session, tenant, user)
    assert archive.read(UEBERSICHT).startswith(b"%PDF-")


async def test_the_readable_csv_is_not_the_import_file(db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant, text="Lieferant AG")
    archive = await make_pack(db_session, tenant, user)
    csv_text = archive.read(BUCHUNGEN_CSV).decode()
    # Semicolons and a header a person can read — opening the Banana TSV in
    # Excel is how a hand-off gets silently modified.
    assert csv_text.startswith("Nr;Datum;Beschreibung")
    assert "Lieferant AG" in csv_text


# --- the part that makes it useful ----------------------------------------


async def test_a_booking_without_a_receipt_is_named_in_the_readme(db_session, actor):
    tenant, user, _headers = actor
    with_receipt = await add_booking(db_session, tenant, text="Mit Beleg")
    await attach_document(db_session, tenant, with_receipt)
    await add_booking(db_session, tenant, text="Ohne Beleg", betrag=240.0)
    archive = await make_pack(db_session, tenant, user)
    readme = archive.read(LIESMICH).decode()
    assert "Ohne Beleg — das ist die Liste" in readme
    assert "Ohne Beleg" in readme
    assert "240.00" in readme
    assert "Belege vorhanden:  1 von 2" in readme


async def test_a_receipt_whose_file_is_gone_is_reported_not_swallowed(db_session, actor):
    tenant, user, _headers = actor
    booking = await add_booking(db_session, tenant)
    document = await attach_document(db_session, tenant, booking)
    get_storage().delete(document.file_key)
    archive = await make_pack(db_session, tenant, user)
    readme = archive.read(LIESMICH).decode()
    # The one failure that is invisible from the booking alone: the system
    # believes there is a receipt and there is not.
    assert "Datei nicht lesbar" in readme
    assert not [n for n in archive.namelist() if n.startswith(f"{BELEGE_DIR}/")]


async def test_the_readme_says_what_is_not_in_the_pack(db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant)
    archive = await make_pack(db_session, tenant, user)
    readme = archive.read(LIESMICH).decode()
    assert "Eröffnungsbilanz" in readme
    assert "Nicht enthalten" in readme


async def test_the_csv_points_at_the_receipt_file(db_session, actor):
    tenant, user, _headers = actor
    booking = await add_booking(db_session, tenant)
    await attach_document(db_session, tenant, booking, vendor="Migros")
    archive = await make_pack(db_session, tenant, user)
    assert "001-Migros.pdf" in archive.read(BUCHUNGEN_CSV).decode()


# --- the route ------------------------------------------------------------


async def test_the_route_returns_a_zip(client, db_session, actor):
    tenant, user, headers = actor
    booking = await add_booking(db_session, tenant)
    await attach_document(db_session, tenant, booking)
    batch = await ExportBatchService(db_session, user).create()
    res = await client.get(f"/api/export/batches/{batch.id}/pack.zip", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "Treuhand-Muster-GmbH-" in res.headers["content-disposition"]
    assert zipfile.ZipFile(io.BytesIO(res.content)).read(LIESMICH)


async def test_building_the_pack_changes_nothing(client, db_session, actor):
    tenant, user, headers = actor
    await add_booking(db_session, tenant)
    batch = await ExportBatchService(db_session, user).create()
    before = (batch.checksum, batch.booking_count)
    await client.get(f"/api/export/batches/{batch.id}/pack.zip", headers=headers)
    await client.get(f"/api/export/batches/{batch.id}/pack.zip", headers=headers)
    await db_session.refresh(batch)
    # A Treuhänder who loses the e-mail gets the same zip again.
    assert (batch.checksum, batch.booking_count) == before


async def test_another_tenants_batch_is_not_found(client, db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant)
    batch = await ExportBatchService(db_session, user).create()
    other = await create_tenant(db_session, name="Fremd AG")
    other_user = await create_user(db_session, other, role="editor")
    res = await client.get(f"/api/export/batches/{batch.id}/pack.zip", headers=auth_headers(other_user))
    assert res.status_code == 404


async def test_the_pack_needs_a_token(client, db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant)
    batch = await ExportBatchService(db_session, user).create()
    assert (await client.get(f"/api/export/batches/{batch.id}/pack.zip")).status_code in (401, 403)


async def test_the_csv_amount_is_a_number_a_spreadsheet_can_add(db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant, betrag=1800.0)
    archive = await make_pack(db_session, tenant, user)
    # 1'800.00 with a thousands separator makes the cell text, and the first
    # thing anyone does with this file is sum a column.
    assert ";1800.00;" in archive.read(BUCHUNGEN_CSV).decode()


async def test_a_description_excel_would_run_is_neutralised(db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant, text="=1+1 Lieferant")
    archive = await make_pack(db_session, tenant, user)
    row = next(line for line in archive.read(BUCHUNGEN_CSV).decode().splitlines() if "Lieferant" in line)
    assert "'=1+1 Lieferant" in row


async def test_the_readme_lists_the_parts_in_a_readable_column(db_session, actor):
    tenant, user, _headers = actor
    await add_booking(db_session, tenant)
    archive = await make_pack(db_session, tenant, user)
    inhalt = [line for line in archive.read(LIESMICH).decode().splitlines() if line.startswith("  10-")]
    assert inhalt and inhalt[0].startswith(f"  {UEBERSICHT}  ")
