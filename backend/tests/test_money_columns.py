"""B-51 — money columns are decimal in the database and rounded on the way in.

The bug this closes is quiet: three bookings of 0.10, 0.20 and 0.30 summed to
0.6000000000000001 and the export printed 0.60 while the stats printed the
artefact. Now the column rounds on insert and PostgreSQL adds exactly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from app.models.booking import Booking
from app.models.types import Chf
from tests.conftest import _IS_SQLITE
from tests.factories import auth_headers, create_booking, create_review_item, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


def test_the_column_type_rounds_half_up_on_bind():
    """The rounding lives in the column, so no caller can forget it."""

    class _Pg:
        name = "postgresql"

    class _Other:
        name = "sqlite"

    chf = Chf()
    assert chf.process_bind_param(2.675, _Pg()) == Decimal("2.68")
    assert chf.process_bind_param(0.125, _Pg()) == Decimal("0.13")
    assert chf.process_bind_param(12.345, _Other()) == 12.35
    assert chf.process_bind_param(None, _Pg()) is None
    assert chf.process_result_value(Decimal("12.34"), _Pg()) == 12.34
    assert chf.process_result_value(None, _Pg()) is None


async def test_a_third_decimal_never_reaches_the_database(db_session, actor):
    tenant, _user, _headers = actor
    await create_booking(db_session, tenant, betrag=12.345, mwst_amount=0.926)
    stored = (await db_session.execute(select(Booking).where(Booking.tenant_id == tenant.id))).scalar_one()
    assert stored.betrag == 12.35
    assert stored.mwst_amount == 0.93


async def test_the_review_queue_amount_is_rounded_too(db_session, actor):
    tenant, _user, _headers = actor
    item = await create_review_item(db_session, tenant, betrag=99.999)
    await db_session.refresh(item)
    assert item.betrag == 100.0


@pytest.mark.skipif(_IS_SQLITE, reason="exact decimal arithmetic is a PostgreSQL property")
async def test_postgres_adds_francs_without_binary_drift(db_session, actor):
    tenant, _user, _headers = actor
    for amount in (0.1, 0.2, 0.3):
        await create_booking(db_session, tenant, betrag=amount)

    # The database adds the column, not Python: ask it in its own words first.
    exact = await db_session.scalar(
        text("SELECT SUM(betrag)::text FROM bookings WHERE tenant_id = :t").bindparams(t=tenant.id)
    )
    assert exact == "0.60"  # not 0.6000000000000001

    total = await db_session.scalar(select(func.sum(Booking.betrag)).where(Booking.tenant_id == tenant.id))
    assert total == 0.6


async def test_the_stats_endpoint_reports_a_clean_total(client, db_session, actor):
    tenant, _user, headers = actor
    for amount in (0.1, 0.2, 0.3):
        await create_booking(db_session, tenant, betrag=amount)

    body = (await client.get("/api/bookings/stats", headers=headers)).json()
    assert body["total_amount"] == 0.6


async def test_the_export_still_sees_plain_floats(client, db_session, actor):
    """Every service works in float; the decimal stays inside the database."""
    tenant, _user, headers = actor
    await create_booking(db_session, tenant, betrag=1234.5, beschreibung="Beratung")

    response = await client.get("/api/export/csv", headers=headers)
    assert response.status_code == 200
    assert "1234.5" in response.text or "1234.50" in response.text
