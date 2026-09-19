"""Banana batch export (phase 4): checklist, one hand-off, idempotent re-download, isolation."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.bank_transaction import TX_STATUS_OFFEN, BankTransaction
from app.models.booking import Booking
from app.models.document import STATUS_BEZAHLT, STATUS_EXPORTIERT, STATUS_OFFEN, Document
from app.models.export_batch import ExportBatch
from app.services.export_batch import (
    ExportBatchService,
    duplicate_ids,
    render_banana,
    render_cover_sheet,
    vat_disagrees,
)
from tests.factories import auth_headers, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


async def add_booking(
    db,
    tenant,
    *,
    datum="05.04.2026",
    betrag=100.0,
    soll="4000",
    haben="1020",
    code="I81",
    pct="8.10",
    mwst=7.49,
    text="Lieferant AG",
) -> Booking:
    booking = Booking(
        tenant_id=tenant.id,
        datum=datum,
        beschreibung=text,
        betrag=betrag,
        kt_soll=soll,
        kt_haben=haben,
        mwst_code=code,
        mwst_pct=pct,
        mwst_amount=mwst,
        source="abgleich",
    )
    db.add(booking)
    await db.flush()
    return booking


# ── pure helpers ─────────────────────────────────────────────────────────────


def test_vat_disagrees_only_when_code_and_rate_conflict():
    ok = Booking(mwst_pct="8.10", mwst_code="I81")
    kept = Booking(mwst_pct="8.10", mwst_code="M81")  # same rate, Umsatzsteuer side
    no_vat = Booking(mwst_pct="", mwst_code="")
    zero = Booking(mwst_pct="0.00", mwst_code="")
    wrong = Booking(mwst_pct="8.10", mwst_code="I26")
    unknown_rate = Booking(mwst_pct="5.00", mwst_code="I50")
    junk = Booking(mwst_pct="acht", mwst_code="I81")
    assert not vat_disagrees(ok)
    assert not vat_disagrees(kept)
    assert not vat_disagrees(no_vat)
    assert not vat_disagrees(zero)
    assert vat_disagrees(wrong)
    assert vat_disagrees(unknown_rate)
    assert vat_disagrees(junk)


def test_duplicate_ids_pairs_same_day_amount_accounts():
    rows = [
        Booking(id=1, datum="05.04.2026", betrag=100.0, kt_soll="4000", kt_haben="1020"),
        Booking(id=2, datum="05.04.2026", betrag=100.0, kt_soll="4000", kt_haben="1020"),
        Booking(id=3, datum="06.04.2026", betrag=100.0, kt_soll="4000", kt_haben="1020"),
    ]
    assert duplicate_ids(rows) == [1, 2]


def test_render_banana_is_stable_and_swiss_dates_become_iso():
    rows = [Booking(id=7, datum="05.04.2026", beschreibung="Miete", kt_soll="6000", kt_haben="1020", betrag=350.0)]
    content = render_banana(rows)
    lines = content.splitlines()
    assert lines[0].split("\t") == ["Date", "Description", "AccountDebit", "AccountCredit", "Amount", "VatCode"]
    assert lines[1].startswith("2026-04-05\tMiete\t6000\t1020\t350.00")
    assert render_banana(rows) == content


def test_cover_sheet_names_company_total_and_accounts():
    batch = ExportBatch(
        id=3,
        filename="banana_2026-09-15_3.txt",
        booking_count=2,
        total_betrag=1234.5,
        total_mwst=92.55,
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        checksum="abc123",
        note="April",
        created_at=datetime(2026, 9, 15, 14, 30, tzinfo=UTC),
    )
    rows = [
        Booking(id=1, datum="01.04.2026", betrag=1000.0, kt_soll="4000", kt_haben="1020"),
        Booking(id=2, datum="30.04.2026", betrag=234.5, kt_soll="6000", kt_haben="1020"),
    ]
    sheet = render_cover_sheet(batch, rows, company="Muster GmbH")
    assert "Muster GmbH" in sheet
    assert "01.04.2026 – 30.04.2026" in sheet
    assert "1'234.50" in sheet
    assert "4000" in sheet and "6000" in sheet
    assert "abc123" in sheet
    assert "Notiz: April" in sheet


# ── service ──────────────────────────────────────────────────────────────────


async def test_preflight_is_green_and_ready_for_clean_bookings(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant)
    await add_booking(db_session, tenant, datum="06.04.2026", betrag=200.0, mwst=14.99)

    pre = await ExportBatchService(db_session, user).preflight()
    assert pre.exportable == 2
    assert pre.total == 300.0
    assert pre.period_from == date(2026, 4, 5)
    assert pre.period_to == date(2026, 4, 6)
    assert pre.blockers == 0
    assert pre.ready is True
    assert all(c.count == 0 for c in pre.checks)


async def test_preflight_flags_every_blocker_with_booking_ids(db_session, actor):
    tenant, user, _ = actor
    no_account = await add_booking(db_session, tenant, haben="")
    zero = await add_booking(db_session, tenant, betrag=0.0, mwst=0.0)
    bad_date = await add_booking(db_session, tenant, datum="irgendwann")
    wrong_vat = await add_booking(db_session, tenant, code="I26")

    pre = await ExportBatchService(db_session, user).preflight()
    flagged = {c.code: c for c in pre.checks}
    assert flagged["konten_fehlen"].booking_ids == [no_account.id]
    assert flagged["betrag_null"].booking_ids == [zero.id]
    assert flagged["datum_fehlt"].booking_ids == [bad_date.id]
    assert flagged["mwst_unstimmig"].booking_ids == [wrong_vat.id]
    assert pre.blockers == 4
    assert pre.ready is False


async def test_preflight_warns_about_open_lines_and_overdue_documents(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant)
    db_session.add(
        BankTransaction(
            tenant_id=tenant.id,
            status=TX_STATUS_OFFEN,
            value_date=date(2026, 4, 7),
            description="E-Banking",
            amount=-80.0,
            currency="CHF",
            dedup_key="k1",
        )
    )
    db_session.add(
        Document(
            tenant_id=tenant.id,
            status=STATUS_OFFEN,
            file_key="receipts/1/a.pdf",
            filename="a.pdf",
            vendor="Spät AG",
            amount=80.0,
            due_date=datetime.now(UTC).date() - timedelta(days=5),
        )
    )
    await db_session.flush()

    pre = await ExportBatchService(db_session, user).preflight()
    flagged = {c.code: c for c in pre.checks}
    assert flagged["offene_bankzeilen"].count == 1
    assert flagged["ueberfaellige_dokumente"].count == 1
    assert pre.blockers == 0  # warnings never block
    assert pre.ready is True


async def test_create_stamps_bookings_and_marks_documents_exported(db_session, actor):
    tenant, user, _ = actor
    booking = await add_booking(db_session, tenant)
    doc = Document(
        tenant_id=tenant.id,
        status=STATUS_BEZAHLT,
        file_key="receipts/1/b.pdf",
        filename="b.pdf",
        vendor="Lieferant AG",
        amount=100.0,
        booking_id=booking.id,
    )
    db_session.add(doc)
    await db_session.flush()

    batch = await ExportBatchService(db_session, user).create(note="April 2026")
    await db_session.flush()

    assert batch.booking_count == 1
    assert batch.total_betrag == 100.0
    assert batch.filename.endswith(f"_{batch.id}.txt")
    assert len(batch.checksum) == 64
    assert booking.export_batch_id == batch.id
    assert booking.exported_at is not None
    assert doc.status == STATUS_EXPORTIERT


async def test_second_export_only_takes_the_new_bookings(db_session, actor):
    tenant, user, _ = actor
    service = ExportBatchService(db_session, user)
    await add_booking(db_session, tenant)
    first = await service.create()
    assert first.booking_count == 1

    # Nothing new → nothing to export.
    with pytest.raises(Exception) as exc:
        await service.create()
    assert "Keine neuen Buchungen" in str(exc.value.detail)

    await add_booking(db_session, tenant, datum="10.04.2026", betrag=50.0, mwst=3.75)
    second = await service.create()
    assert second.booking_count == 1
    assert second.id != first.id
    _, content = await service.content(second.id)
    assert len(content.splitlines()) == 2  # header + the one new row


async def test_redownload_renders_the_same_bytes(db_session, actor):
    tenant, user, _ = actor
    service = ExportBatchService(db_session, user)
    await add_booking(db_session, tenant)
    batch = await service.create()
    _, once = await service.content(batch.id)
    _, twice = await service.content(batch.id)
    assert once == twice
    import hashlib

    assert hashlib.sha256(once.encode("utf-8")).hexdigest() == batch.checksum


async def test_create_refuses_while_a_blocker_is_open(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant, soll="")
    with pytest.raises(Exception) as exc:
        await ExportBatchService(db_session, user).create()
    assert exc.value.status_code == 409
    assert "Soll- und Habenkonto" in str(exc.value.detail)
    assert (await db_session.execute(select(ExportBatch))).scalars().first() is None


# ── HTTP ─────────────────────────────────────────────────────────────────────


async def test_http_flow_preflight_export_download_cover(client, db_session, actor):
    tenant, _, headers = actor
    await add_booking(db_session, tenant)
    await db_session.commit()

    pre = await client.get("/api/export/batches/preflight", headers=headers)
    assert pre.status_code == 200
    assert pre.json()["exportable"] == 1
    assert pre.json()["ready"] is True
    assert len(pre.json()["checks"]) == 7

    created = await client.post("/api/export/batches/", headers=headers, json={"note": "April"})
    assert created.status_code == 200
    batch_id = created.json()["id"]
    assert created.json()["booking_count"] == 1

    listed = await client.get("/api/export/batches/", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    file_res = await client.get(f"/api/export/batches/{batch_id}/file", headers=headers)
    assert file_res.status_code == 200
    assert file_res.text.splitlines()[0].startswith("Date\t")
    assert "attachment" in file_res.headers["content-disposition"]

    cover = await client.get(f"/api/export/batches/{batch_id}/cover", headers=headers)
    assert cover.status_code == 200
    assert "Banana-Import" in cover.text

    again = await client.post("/api/export/batches/", headers=headers)
    assert again.status_code == 404


async def test_viewer_may_look_but_not_export(client, db_session, actor):
    tenant, _, _ = actor
    viewer = await create_user(db_session, tenant, role="viewer")
    await add_booking(db_session, tenant)
    await db_session.commit()
    headers = auth_headers(viewer)

    assert (await client.get("/api/export/batches/preflight", headers=headers)).status_code == 200
    assert (await client.post("/api/export/batches/", headers=headers)).status_code == 403


async def test_another_tenant_cannot_see_or_download_the_batch(client, db_session, actor):
    tenant, _user, headers = actor
    await add_booking(db_session, tenant)
    await db_session.commit()
    batch_id = (await client.post("/api/export/batches/", headers=headers)).json()["id"]

    other_tenant = await create_tenant(db_session)
    other = await create_user(db_session, other_tenant, role="owner")
    other_headers = auth_headers(other)

    assert (await client.get("/api/export/batches/", headers=other_headers)).json()["count"] == 0
    assert (await client.get(f"/api/export/batches/{batch_id}", headers=other_headers)).status_code == 404
    assert (await client.get(f"/api/export/batches/{batch_id}/file", headers=other_headers)).status_code == 404
    assert (await client.get(f"/api/export/batches/{batch_id}/cover", headers=other_headers)).status_code == 404


async def test_export_requires_a_login(client):
    assert (await client.get("/api/export/batches/preflight")).status_code == 401
    assert (await client.post("/api/export/batches/")).status_code == 401
