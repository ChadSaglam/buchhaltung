"""Monatsabschluss-Check (B-66): movement check, month scoping, red/green list, isolation."""

from __future__ import annotations

from datetime import date

import pytest

from app.models.bank_transaction import (
    TX_STATUS_GEBUCHT,
    TX_STATUS_IGNORIERT,
    TX_STATUS_OFFEN,
    BankTransaction,
)
from app.models.booking import Booking
from app.models.document import STATUS_OFFEN, Document
from app.models.export_batch import ExportBatch
from app.services.monatsabschluss import (
    MonatsabschlussService,
    default_month,
    is_expense,
    is_revenue,
    month_bounds,
    month_key,
    month_label,
    signed_bank_effect,
)
from tests.factories import auth_headers, create_tenant, create_user

APRIL = "2026-04"


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
    source_key="receipts/1/a.pdf",
    batch_id=None,
) -> Booking:
    booking = Booking(
        tenant_id=tenant.id,
        datum=datum,
        beschreibung="Lieferant AG",
        betrag=betrag,
        kt_soll=soll,
        kt_haben=haben,
        mwst_code=code,
        mwst_pct=pct,
        mwst_amount=0.0,
        source="abgleich",
        source_key=source_key,
        export_batch_id=batch_id,
    )
    db.add(booking)
    await db.flush()
    return booking


async def add_tx(db, tenant, *, day="2026-04-05", amount=-100.0, status=TX_STATUS_GEBUCHT, key="k") -> BankTransaction:
    tx = BankTransaction(
        tenant_id=tenant.id,
        status=status,
        value_date=date.fromisoformat(day),
        booking_date=date.fromisoformat(day),
        description="E-Banking",
        amount=amount,
        currency="CHF",
        dedup_key=f"{key}-{amount}-{day}",
    )
    db.add(tx)
    await db.flush()
    return tx


# ── pure helpers ─────────────────────────────────────────────────────────────


def test_month_bounds_and_label():
    assert month_bounds("2026-04") == (date(2026, 4, 1), date(2026, 4, 30))
    assert month_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert month_label("2026-04") == "April 2026"
    assert month_key(date(2026, 4, 5)) == "2026-04"
    assert month_key(None) is None


def test_a_bad_month_is_a_clear_400():
    with pytest.raises(Exception) as exc:
        month_bounds("April")
    assert exc.value.status_code == 400
    assert "JJJJ-MM" in str(exc.value.detail)


def test_signed_bank_effect_follows_the_side_the_bank_is_on():
    out = Booking(betrag=100.0, kt_soll="4000", kt_haben="1020")
    into = Booking(betrag=250.0, kt_soll="1020", kt_haben="3000")
    elsewhere = Booking(betrag=80.0, kt_soll="4000", kt_haben="2000")
    both = Booking(betrag=80.0, kt_soll="1020", kt_haben="1020")
    assert signed_bank_effect(out) == -100.0
    assert signed_bank_effect(into) == 250.0
    assert signed_bank_effect(elsewhere) == 0.0
    assert signed_bank_effect(both) == 0.0


def test_revenue_and_expense_read_the_swiss_chart():
    assert is_revenue(Booking(kt_haben="3000"))
    assert not is_revenue(Booking(kt_haben="1020"))
    assert is_expense(Booking(kt_soll="4000"))
    assert is_expense(Booking(kt_soll="6500"))
    assert not is_expense(Booking(kt_soll="1020"))


def test_default_month_is_the_newest_with_data_else_today():
    assert default_month([date(2026, 3, 9), date(2026, 4, 1)]) == "2026-04"
    assert default_month([], today=date(2026, 9, 15)) == "2026-09"


# ── service ──────────────────────────────────────────────────────────────────


async def test_a_clean_month_is_green(db_session, actor):
    tenant, user, _ = actor
    batch = ExportBatch(tenant_id=tenant.id, booking_count=1)
    db_session.add(batch)
    await db_session.flush()
    await add_booking(db_session, tenant, betrag=100.0, batch_id=batch.id)
    await add_tx(db_session, tenant, amount=-100.0)

    report = await MonatsabschlussService(db_session, user).report(APRIL)
    assert report.monat == APRIL
    assert report.label == "April 2026"
    assert report.kpis.bank_bewegung == -100.0
    assert report.kpis.konto_1020_bewegung == -100.0
    assert report.kpis.differenz == 0.0
    assert report.blockers == 0
    assert report.warnings == 0
    assert report.ready is True


async def test_a_missing_booking_shows_up_as_a_difference(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant, betrag=100.0)
    await add_tx(db_session, tenant, amount=-100.0, key="a")
    await add_tx(db_session, tenant, amount=-40.0, key="b")  # nobody booked this one

    report = await MonatsabschlussService(db_session, user).report(APRIL)
    check = next(c for c in report.checks if c.code == "bank_stimmt")
    assert check.count == 1
    assert "40.00" in check.detail
    assert report.ready is False


async def test_ignored_bank_lines_count_for_nothing(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant, betrag=100.0)
    await add_tx(db_session, tenant, amount=-100.0, key="a")
    await add_tx(db_session, tenant, amount=-999.0, status=TX_STATUS_IGNORIERT, key="ignored")

    report = await MonatsabschlussService(db_session, user).report(APRIL)
    assert report.kpis.bank_bewegung == -100.0
    assert next(c for c in report.checks if c.code == "bank_stimmt").count == 0
    assert next(c for c in report.checks if c.code == "bankzeilen_offen").count == 0


async def test_open_bank_lines_block_the_month(db_session, actor):
    tenant, user, _ = actor
    await add_tx(db_session, tenant, amount=-100.0, status=TX_STATUS_OFFEN)

    report = await MonatsabschlussService(db_session, user).report(APRIL)
    check = next(c for c in report.checks if c.code == "bankzeilen_offen")
    assert check.count == 1
    assert report.blockers >= 1
    assert report.ready is False


async def test_warnings_never_block_but_are_named(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant, betrag=100.0, source_key="")  # no receipt, not exported
    await add_tx(db_session, tenant, amount=-100.0)
    db_session.add(
        Document(
            tenant_id=tenant.id,
            status=STATUS_OFFEN,
            file_key="receipts/1/open.pdf",
            filename="open.pdf",
            vendor="Spät AG",
            amount=80.0,
            due_date=date(2026, 4, 20),
        )
    )
    await db_session.flush()

    report = await MonatsabschlussService(db_session, user).report(APRIL)
    flagged = {c.code: c for c in report.checks}
    assert flagged["beleg_fehlt"].count == 1
    assert flagged["dokumente_faellig"].count == 1
    assert flagged["nicht_exportiert"].count == 1
    assert report.blockers == 0
    assert report.warnings == 3
    assert report.ready is True


async def test_only_the_asked_month_is_looked_at(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant, datum="05.04.2026", betrag=100.0)
    await add_tx(db_session, tenant, day="2026-04-05", amount=-100.0, key="apr")
    await add_booking(db_session, tenant, datum="10.05.2026", betrag=60.0)
    await add_tx(db_session, tenant, day="2026-05-10", amount=-60.0, key="mai")

    service = MonatsabschlussService(db_session, user)
    april = await service.report("2026-04")
    mai = await service.report("2026-05")
    assert (april.kpis.buchungen, april.kpis.bank_bewegung) == (1, -100.0)
    assert (mai.kpis.buchungen, mai.kpis.bank_bewegung) == (1, -60.0)
    assert await service.months() == ["2026-05", "2026-04"]


async def test_revenue_and_expense_kpis(db_session, actor):
    tenant, user, _ = actor
    await add_booking(db_session, tenant, betrag=1000.0, soll="1020", haben="3000")
    await add_booking(db_session, tenant, betrag=300.0, soll="4000", haben="1020")
    await add_tx(db_session, tenant, amount=1000.0, key="in")
    await add_tx(db_session, tenant, amount=-300.0, key="out")

    report = await MonatsabschlussService(db_session, user).report(APRIL)
    assert report.kpis.einnahmen == 1000.0
    assert report.kpis.ausgaben == 300.0
    assert report.kpis.differenz == 0.0


# ── HTTP ─────────────────────────────────────────────────────────────────────


async def test_http_months_and_report(client, db_session, actor):
    tenant, _, headers = actor
    await add_booking(db_session, tenant, betrag=100.0)
    await add_tx(db_session, tenant, amount=-100.0)
    await db_session.commit()

    months = await client.get("/api/abschluss/monate", headers=headers)
    assert months.status_code == 200
    assert months.json()["monate"] == [APRIL]
    assert months.json()["labels"][APRIL] == "April 2026"
    assert months.json()["aktuell"] == APRIL

    report = await client.get("/api/abschluss/monat", headers=headers)  # no month → newest
    assert report.status_code == 200
    assert report.json()["monat"] == APRIL
    assert len(report.json()["checks"]) == 7
    assert report.json()["kpis"]["differenz"] == 0.0

    asked = await client.get(f"/api/abschluss/monat?monat={APRIL}", headers=headers)
    assert asked.json()["label"] == "April 2026"

    bad = await client.get("/api/abschluss/monat?monat=April", headers=headers)
    assert bad.status_code == 400


async def test_empty_tenant_gets_the_current_month_and_no_blockers(client, db_session, actor):
    _tenant, _, headers = actor
    await db_session.commit()

    months = await client.get("/api/abschluss/monate", headers=headers)
    assert months.json()["monate"] == []
    report = await client.get("/api/abschluss/monat", headers=headers)
    assert report.status_code == 200
    assert report.json()["ready"] is True
    assert report.json()["kpis"]["buchungen"] == 0


async def test_another_tenant_sees_its_own_month_only(client, db_session, actor):
    tenant, _, headers = actor
    await add_booking(db_session, tenant, betrag=100.0)
    await add_tx(db_session, tenant, amount=-100.0)
    other_tenant = await create_tenant(db_session)
    other = await create_user(db_session, other_tenant, role="owner")
    await db_session.commit()

    mine = await client.get("/api/abschluss/monat?monat=2026-04", headers=headers)
    theirs = await client.get("/api/abschluss/monat?monat=2026-04", headers=auth_headers(other))
    assert mine.json()["kpis"]["buchungen"] == 1
    assert theirs.json()["kpis"]["buchungen"] == 0
    assert theirs.json()["kpis"]["bank_bewegung"] == 0.0
    assert (await client.get("/api/abschluss/monat")).status_code == 401
    assert (await client.get("/api/abschluss/monate")).status_code == 401
