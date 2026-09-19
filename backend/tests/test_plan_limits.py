"""Plan limits (B-23).

Two halves. The first holds the *declaration* against the code: a limit whose
event nobody writes is a limit that never fires, and it would look perfectly
healthy in review. The second drives the real endpoints past the ceiling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.plans import (
    BESTAND,
    EVENT_TYPE,
    LIMIT_KEYS,
    LIMIT_LABEL,
    MONATLICH,
    PLAN_FALLBACK,
    PLANS,
    limits_for,
)
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent
from app.services.plan_limits import MB, PlanLimits, monatsbeginn
from app.services.storage_quota import StorageQuota
from tests.factories import auth_headers, create_tenant, create_user

pytestmark = pytest.mark.asyncio

APP_DIR = Path(__file__).resolve().parents[1] / "app"


# --------------------------------------------------------------------------- #
# The declaration, held against the code
# --------------------------------------------------------------------------- #


async def test_every_limit_has_an_event_a_label_and_a_period():
    for key in LIMIT_KEYS:
        assert key in EVENT_TYPE, f"{key} counts nothing"
        assert key in LIMIT_LABEL, f"{key} has no name a customer could read"
        assert (key in MONATLICH) != (key in BESTAND), f"{key} must be monthly or a stock, not both or neither"


async def test_every_plan_answers_every_limit():
    for plan, limits in PLANS.items():
        assert set(limits) == set(LIMIT_KEYS), f"plan {plan} does not cover {set(LIMIT_KEYS) ^ set(limits)}"


def _app_lines() -> list[str]:
    return [line for path in APP_DIR.rglob("*.py") for line in path.read_text(encoding="utf-8").splitlines()]


async def test_every_counted_event_is_actually_written_somewhere():
    """A limit nobody records is a limit that never fires — and it reviews clean."""
    lines = _app_lines()
    for key, event in EVENT_TYPE.items():
        writers = [
            line
            for line in lines
            if f'"{event}"' in line and (".record(" in line or "STORAGE_EVENT" in line or "event_type=" in line)
        ]
        assert writers, f"nothing in app/ writes a '{event}' usage event, so the '{key}' limit can never trigger"


async def test_free_is_never_more_generous_than_pro():
    for key in LIMIT_KEYS:
        free, pro = PLANS["free"][key], PLANS["pro"][key]
        if free is None:
            assert pro is None, f"free is unlimited on {key} but pro is not"
        elif pro is not None:
            assert free <= pro, f"free gets more {key} than pro"


async def test_an_unknown_plan_falls_back_to_free_not_to_unlimited():
    assert limits_for("whatever-billing-invents-next") == PLANS[PLAN_FALLBACK]
    assert limits_for(None) == PLANS[PLAN_FALLBACK]
    assert limits_for("") == PLANS[PLAN_FALLBACK]
    assert limits_for("PRO") == PLANS["pro"], "the plan string is compared case-insensitively"


async def test_the_month_starts_in_zurich_not_in_utc():
    """01.02. 00:30 in Zurich is still January in UTC. The customer's month wins."""
    zurich = ZoneInfo("Europe/Zurich")
    kurz_nach_mitternacht = datetime(2026, 2, 1, 0, 30, tzinfo=zurich)

    start = monatsbeginn(kurz_nach_mitternacht)

    assert start.astimezone(zurich).month == 2
    assert start.astimezone(zurich).day == 1
    assert start < kurz_nach_mitternacht


# --------------------------------------------------------------------------- #
# Counting
# --------------------------------------------------------------------------- #


async def _event(db, tenant, event_type: str, quantity: int, when: datetime | None = None) -> None:
    row = UsageEvent(tenant_id=tenant.id, event_type=event_type, quantity=quantity)
    if when is not None:
        row.created_at = when
    db.add(row)
    await db.flush()


async def _upload(client, user):
    return await client.post(
        "/api/documents/",
        headers=auth_headers(user),
        files={"files": ("beleg.pdf", b"%PDF-1.4 not really a pdf", "application/pdf")},
    )


async def _set_plan(db, tenant, plan: str) -> None:
    tenant.subscription_plan = plan
    await db.flush()


async def test_last_months_usage_does_not_count_against_this_month(db_session):
    tenant = await create_tenant(db_session)
    letzter_monat = monatsbeginn() - timedelta(days=2)
    await _event(db_session, tenant, "beleg", 5, when=letzter_monat)
    await _event(db_session, tenant, "beleg", 2)

    verbrauch = await PlanLimits(tenant.id, db_session).verbrauch()

    assert verbrauch["belege"] == 2


async def test_storage_is_a_stock_and_does_not_reset(db_session):
    tenant = await create_tenant(db_session)
    letzter_monat = monatsbeginn() - timedelta(days=2)
    await _event(db_session, tenant, "storage_bytes", 3 * MB, when=letzter_monat)
    await _event(db_session, tenant, "storage_bytes", 1 * MB)

    verbrauch = await PlanLimits(tenant.id, db_session).verbrauch()

    assert verbrauch["speicher_mb"] == 4


async def test_a_single_byte_over_a_megabyte_counts_as_the_next_megabyte(db_session):
    """Rounded up, so "over the limit" reads as over the limit."""
    tenant = await create_tenant(db_session)
    await _event(db_session, tenant, "storage_bytes", MB + 1)

    assert (await PlanLimits(tenant.id, db_session).verbrauch())["speicher_mb"] == 2


async def test_usage_of_one_tenant_is_not_usage_of_another(db_session):
    one = await create_tenant(db_session)
    two = await create_tenant(db_session)
    await _event(db_session, one, "beleg", 7)

    assert (await PlanLimits(two.id, db_session).verbrauch())["belege"] == 0


async def test_counting_is_one_statement(db_session, counted):
    tenant = await create_tenant(db_session)
    counted.statements.clear()

    await PlanLimits(tenant.id, db_session).verbrauch()

    assert counted.against("usage_events") == 1


# --------------------------------------------------------------------------- #
# Refusing
# --------------------------------------------------------------------------- #


async def test_ensure_refuses_with_402_and_a_code_the_frontend_can_branch_on(db_session):
    from app.core.errors import ApiError

    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "free")
    await _event(db_session, tenant, "beleg", PLANS["free"]["belege"])

    with pytest.raises(ApiError) as exc:
        await PlanLimits(tenant.id, db_session).ensure("belege")

    assert exc.value.status_code == 402
    assert exc.value.code == "plan_limit_erreicht"
    assert "Belege pro Monat" in exc.value.detail


async def test_the_last_one_inside_the_limit_is_allowed(db_session):
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "free")
    await _event(db_session, tenant, "beleg", PLANS["free"]["belege"] - 1)

    await PlanLimits(tenant.id, db_session).ensure("belege")  # must not raise


async def test_an_unlimited_plan_never_refuses(db_session):
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "enterprise")
    await _event(db_session, tenant, "beleg", 10_000)

    await PlanLimits(tenant.id, db_session).ensure("belege")


async def test_the_kill_switch_stops_refusing_but_keeps_counting(db_session, monkeypatch):
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "free")
    await _event(db_session, tenant, "beleg", PLANS["free"]["belege"] + 50)
    monkeypatch.setattr(settings, "ENFORCE_PLAN_LIMITS", False)

    await PlanLimits(tenant.id, db_session).ensure("belege")  # must not raise

    snapshot = await PlanLimits(tenant.id, db_session).snapshot()
    belege = next(z for z in snapshot["zaehler"] if z["key"] == "belege")
    assert snapshot["durchgesetzt"] is False
    assert belege["erreicht"] is True, "still reported, just not enforced"


async def test_ensure_rejects_a_limit_nobody_declared(db_session):
    tenant = await create_tenant(db_session)
    with pytest.raises(AssertionError):
        await PlanLimits(tenant.id, db_session).ensure("erfundene_grenze")


# --------------------------------------------------------------------------- #
# Storage — two ceilings, the smaller wins
# --------------------------------------------------------------------------- #


async def test_the_plan_can_be_stricter_than_the_installation(db_session, monkeypatch):
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "free")  # 1024 MB
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 50_000)

    assert await StorageQuota(tenant.id, db_session).limit_bytes() == PLANS["free"]["speicher_mb"] * MB


async def test_the_installation_can_be_stricter_than_the_plan(db_session, monkeypatch):
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "enterprise")  # unlimited
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 10)

    assert await StorageQuota(tenant.id, db_session).limit_bytes() == 10 * MB


async def test_no_plan_limit_and_no_install_limit_means_no_quota(db_session, monkeypatch):
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "enterprise")
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 0)

    assert await StorageQuota(tenant.id, db_session).limit_bytes() == 0


async def test_an_install_quota_of_zero_beats_the_plan(db_session, monkeypatch):
    """B-54 documents 0 as "no quota". B-23 must not quietly give it one back."""
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "free")  # 1024 MB
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 0)

    assert await StorageQuota(tenant.id, db_session).limit_bytes() == 0


async def test_with_enforcement_off_storage_falls_back_to_b54(db_session, monkeypatch):
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "free")
    monkeypatch.setattr(settings, "ENFORCE_PLAN_LIMITS", False)
    monkeypatch.setattr(settings, "MAX_TENANT_STORAGE_MB", 50_000)

    assert await StorageQuota(tenant.id, db_session).limit_bytes() == 50_000 * MB


# --------------------------------------------------------------------------- #
# Through the API
# --------------------------------------------------------------------------- #


async def test_the_usage_endpoint_reports_every_declared_limit(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _event(db_session, tenant, "beleg", 3)

    body = (await client.get("/api/usage", headers=auth_headers(user))).json()

    assert body["plan"] == "free"
    assert {z["key"] for z in body["zaehler"]} == set(LIMIT_KEYS)
    belege = next(z for z in body["zaehler"] if z["key"] == "belege")
    assert belege["benutzt"] == 3
    assert belege["limit"] == PLANS["free"]["belege"]
    assert belege["periode"] == "monat"
    assert belege["warnung"] is False


async def test_the_usage_endpoint_warns_before_the_wall(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _event(db_session, tenant, "beleg", int(PLANS["free"]["belege"] * 0.9))

    body = (await client.get("/api/usage", headers=auth_headers(user))).json()
    belege = next(z for z in body["zaehler"] if z["key"] == "belege")

    assert belege["warnung"] is True
    assert belege["erreicht"] is False


async def test_the_usage_endpoint_needs_a_token(client):
    assert (await client.get("/api/usage")).status_code in (401, 403)


async def test_classifying_past_the_monthly_limit_is_refused(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _event(db_session, tenant, "classify", PLANS["free"]["klassifizierungen"])

    response = await client.post(
        "/api/classify/",
        headers=auth_headers(user),
        json={"beschreibung": "Migros Zürich", "betrag": 42.0},
    )

    assert response.status_code == 402
    assert response.json()["error"]["code"] == "plan_limit_erreicht"


async def test_classifying_inside_the_limit_still_works(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    response = await client.post(
        "/api/classify/",
        headers=auth_headers(user),
        json={"beschreibung": "Migros Zürich", "betrag": 42.0},
    )

    assert response.status_code == 200


async def test_a_refused_classification_is_not_counted(client, db_session):
    """Refusing before the work means the meter does not move either."""
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _event(db_session, tenant, "classify", PLANS["free"]["klassifizierungen"])

    await client.post(
        "/api/classify/",
        headers=auth_headers(user),
        json={"beschreibung": "Migros Zürich", "betrag": 42.0},
    )

    rows = (
        (
            await db_session.execute(
                select(UsageEvent).where(
                    UsageEvent.tenant_id == tenant.id,
                    UsageEvent.event_type == "classify",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "the refused call must not have added a second event"


async def test_uploading_a_receipt_moves_the_beleg_counter(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    before = (await PlanLimits(tenant.id, db_session).verbrauch())["belege"]
    response = await _upload(client, user)
    assert response.status_code == 200, response.text
    after = (await PlanLimits(tenant.id, db_session).verbrauch())["belege"]

    assert after == before + 1


async def test_uploading_past_the_monthly_beleg_limit_is_refused(client, db_session):
    """The upload is a batch, so one refused file is a failed *result*, not a
    failed request — and it carries the code, so the UI does not parse German."""
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _event(db_session, tenant, "beleg", PLANS["free"]["belege"])

    body = (await _upload(client, user)).json()

    assert body["created"] == 0
    assert body["failed"] == 1
    assert body["results"][0]["code"] == "plan_limit_erreicht"
    assert "Belege pro Monat" in body["results"][0]["error"]


async def test_a_receipt_without_a_qr_code_is_stored_once_not_twice(client, db_session, storage_dir):
    """`ingest` stores the file and then asks the scanner to read it. The scanner
    used to store it a second time under a second key — double on disk, double
    against the quota (B-54) and double against the Beleg counter (B-23)."""
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    await _upload(client, user)

    dateien = [p for p in storage_dir.rglob("*") if p.is_file()]
    assert len(dateien) == 1, [p.name for p in dateien]
    assert (await PlanLimits(tenant.id, db_session).verbrauch())["belege"] == 1


async def test_a_refused_upload_stores_nothing(client, db_session, storage_dir):
    """The whole point of checking before writing."""
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _event(db_session, tenant, "beleg", PLANS["free"]["belege"])

    await _upload(client, user)

    stored = list(storage_dir.rglob("*")) if storage_dir.exists() else []
    assert [p for p in stored if p.is_file()] == []


async def test_a_pro_tenant_is_not_stopped_where_free_would_be(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _set_plan(db_session, tenant, "pro")
    await _event(db_session, tenant, "beleg", PLANS["free"]["belege"] + 10)

    body = (await _upload(client, user)).json()

    assert body["results"][0]["code"] == "", body
    assert body["results"][0]["document"] is not None


async def test_the_plan_comes_from_the_tenant_row_not_from_the_token(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    headers = auth_headers(user)
    await _set_plan(db_session, tenant, "enterprise")

    body = (await client.get("/api/usage", headers=headers)).json()

    assert body["plan"] == "enterprise"
    assert all(z["limit"] is None for z in body["zaehler"])


async def test_deactivating_enforcement_lets_an_over_limit_upload_through(client, db_session, monkeypatch):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await _event(db_session, tenant, "beleg", PLANS["free"]["belege"] + 5)
    monkeypatch.setattr(settings, "ENFORCE_PLAN_LIMITS", False)

    body = (await _upload(client, user)).json()

    assert body["results"][0]["code"] == "", body
    assert body["results"][0]["document"] is not None


async def test_the_tenant_table_is_the_only_place_a_plan_lives(db_session):
    """If this ever moves, `PlanLimits.plan()` has to move with it."""
    tenant = await create_tenant(db_session)
    await _set_plan(db_session, tenant, "pro")

    row = (await db_session.execute(select(Tenant.subscription_plan).where(Tenant.id == tenant.id))).scalar_one()

    assert row == "pro"
    assert await PlanLimits(tenant.id, db_session).plan() == "pro"


async def test_a_tenant_that_vanished_gets_the_fallback_plan(db_session):
    """Never 'unlimited' by accident."""
    assert limits_for(await PlanLimits(999_999, db_session).plan()) == PLANS[PLAN_FALLBACK]


async def test_now_is_inside_the_month_it_reports():
    start = monatsbeginn()
    assert start <= datetime.now(UTC)
    assert (datetime.now(UTC) - start) < timedelta(days=32)
