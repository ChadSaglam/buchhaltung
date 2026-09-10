"""AI assistant — the context handed to the LLM uses the same money rounding as the exports (B-05)."""

from __future__ import annotations

import pytest

from app.services.ai_assistant import build_context
from tests.factories import create_booking, create_tenant


@pytest.mark.asyncio
async def test_build_context_rounds_money_half_up(db_session):
    tenant = await create_tenant(db_session)
    await create_booking(db_session, tenant, datum="15.03.2025", betrag=0.125)
    await create_booking(db_session, tenant, datum="20.03.2025", betrag=-2.675)

    ctx = await build_context(tenant.id, db_session)

    assert ctx["stats"]["anzahl_buchungen"] == 2
    assert ctx["stats"]["total_chf"] == -2.55
    assert sorted(b["betrag"] for b in ctx["letzte_buchungen"]) == [-2.68, 0.13]
    (month,) = ctx["monatlich"]
    assert month == {"monat": "2025-03", "einnahmen": 0.13, "ausgaben": 2.68, "anzahl": 2}
