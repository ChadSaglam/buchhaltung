from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.booking import Booking
from app.models.scanner_config import ScannerConfig
from app.services.scanner.scanner_service import ScannerService
from tests.factories import create_tenant, create_user


@pytest.mark.asyncio
async def test_scanner_config_is_tenant_scoped(db_session):
    tenant_a = await create_tenant(db_session, "A")
    tenant_b = await create_tenant(db_session, "B")
    user_a = await create_user(db_session, tenant_a)
    user_b = await create_user(db_session, tenant_b)

    config_a = await ScannerService(db_session, user_a).get_or_create_config_model()
    config_b = await ScannerService(db_session, user_b).get_or_create_config_model()

    assert config_a.tenant_id == tenant_a.id
    assert config_b.tenant_id == tenant_b.id
    assert config_a.id != config_b.id


@pytest.mark.asyncio
async def test_config_query_never_returns_other_tenant(db_session):
    tenant_a = await create_tenant(db_session, "A")
    tenant_b = await create_tenant(db_session, "B")
    user_b = await create_user(db_session, tenant_b)

    await ScannerService(db_session, user_b).get_or_create_config_model()

    stmt = select(ScannerConfig).where(ScannerConfig.tenant_id == tenant_a.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_bookings_are_isolated_by_tenant(db_session):
    tenant_a = await create_tenant(db_session, "A")
    tenant_b = await create_tenant(db_session, "B")

    booking = Booking(
        tenant_id=tenant_a.id,
        beschreibung="Tenant A invoice",
        betrag=100.0,
    )
    db_session.add(booking)
    await db_session.commit()

    stmt = select(Booking).where(Booking.tenant_id == tenant_b.id)
    result = await db_session.execute(stmt)
    assert result.scalars().all() == []
