"""B-13 — /api/health reports deployment facts outside production, only status+version inside."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.routers import health as health_module

FIELDS = {"status", "version", "database", "migration_head", "storage", "worker"}


@pytest.fixture
def health_db(engine, monkeypatch):
    """Point the health check at the test database instead of the app's own engine."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(health_module, "async_session", maker)
    return maker


async def test_health_reports_all_fields_in_development(client, health_db, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "RUN_WORKER_IN_API", True)

    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == FIELDS
    assert body["status"] == "ok"
    assert body["version"] == settings.APP_VERSION
    assert body["database"] == "ok"
    assert body["migration_head"] is None  # create_all schema: no alembic_version table
    assert body["storage"] == "local"
    assert body["worker"] == "in-api"


async def test_health_reports_applied_migration_and_separate_worker(client, health_db, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "RUN_WORKER_IN_API", False)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "S3")
    async with health_db() as session:
        await session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        await session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('55e64308d75f')"))
        await session.commit()
    try:
        body = (await client.get("/api/health")).json()
    finally:
        async with health_db() as session:
            await session.execute(text("DROP TABLE alembic_version"))
            await session.commit()

    assert body["migration_head"] == "55e64308d75f"
    assert body["worker"] == "separate"
    assert body["storage"] == "s3"


async def test_health_is_degraded_when_the_database_is_down(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    @asynccontextmanager
    async def broken():
        raise ConnectionRefusedError("db down")
        yield  # pragma: no cover

    monkeypatch.setattr(health_module, "async_session", broken)
    body = (await client.get("/api/health")).json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert body["migration_head"] is None


async def test_health_is_trimmed_in_production(client, health_db, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    body = (await client.get("/api/health")).json()
    assert body == {"status": "ok", "version": settings.APP_VERSION}


# --- B-61: health that can actually fail ------------------------------------


@asynccontextmanager
async def _broken_session():
    raise RuntimeError("database is gone")
    yield  # pragma: no cover


@asynccontextmanager
async def _hanging_session():
    import asyncio

    await asyncio.sleep(60)
    yield  # pragma: no cover


async def test_liveness_touches_nothing_and_is_always_ok(client, monkeypatch):
    """A liveness probe that asks the database restarts every container at once
    the moment the database hiccups. This one must answer even then."""
    monkeypatch.setattr(health_module, "async_session", _broken_session)

    resp = await client.get("/api/health/live")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readiness_answers_503_when_the_database_is_gone(client, monkeypatch):
    monkeypatch.setattr(health_module, "async_session", _broken_session)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    resp = await client.get("/api/health")

    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


async def test_production_readiness_actually_checks(client, health_db, monkeypatch):
    """Until B-61 production answered a flat {"status": "ok"} without touching
    anything — an instance with no database kept taking traffic."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    resp = await client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": settings.APP_VERSION}


async def test_production_readiness_fails_with_no_database(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(health_module, "async_session", _broken_session)

    resp = await client.get("/api/health")

    assert resp.status_code == 503
    assert resp.json() == {"status": "degraded", "version": settings.APP_VERSION}


async def test_production_readiness_still_leaks_nothing(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(health_module, "async_session", _broken_session)

    body = (await client.get("/api/health")).json()

    assert set(body) == {"status", "version"}


async def test_a_hanging_database_fails_fast_instead_of_hanging_the_probe(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(health_module, "async_session", _hanging_session)
    monkeypatch.setattr(health_module, "DB_TIMEOUT_SECONDS", 0.05)

    resp = await client.get("/api/health")

    assert resp.status_code == 503


async def test_detail_is_open_outside_production(client, health_db, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    resp = await client.get("/api/health/detail")

    assert resp.status_code == 200
    assert "checks" in resp.json()


async def test_detail_needs_a_token_in_production(client, health_db, monkeypatch):
    """It names the upstream and the exception class; that is why it is useful
    and why it does not belong on the open internet."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    assert (await client.get("/api/health/detail")).status_code == 401


async def test_detail_needs_admin_in_production(client, db_session, health_db, monkeypatch):
    from tests.factories import auth_headers, create_tenant, create_user

    tenant = await create_tenant(db_session)
    editor = await create_user(db_session, tenant, role="editor")
    admin = await create_user(db_session, tenant, role="admin")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    assert (await client.get("/api/health/detail", headers=auth_headers(editor))).status_code == 403
    assert (await client.get("/api/health/detail", headers=auth_headers(admin))).status_code == 200


async def test_detail_is_not_503_because_an_optional_service_is_asleep(client, health_db, monkeypatch):
    """Ollama is optional — B-20 says so on the checklist. An instance pulled out
    of the load balancer because the AI service is down would be a worse outage
    than the one it is reporting."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    resp = await client.get("/api/health/detail")

    assert resp.status_code == 200
    assert resp.json()["checks"]["ollama"]["status"] in ("error", "not_configured", "ok")
    assert resp.json()["status"] == "ok"


async def test_detail_is_503_when_something_required_is_broken(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(health_module, "async_session", _broken_session)

    resp = await client.get("/api/health/detail")

    assert resp.status_code == 503
    assert resp.json()["checks"]["database"]["status"] == "error"


async def test_health_is_exempt_from_the_default_rate_limit():
    """A 429 reads as 'unhealthy' to every orchestrator there is."""
    from app.core.rate_limit import is_exempt

    assert is_exempt("/api/health")
    assert is_exempt("/api/health/live")
    assert is_exempt("/api/health/detail")
    assert not is_exempt("/api/healthy-looking-thing")
    assert not is_exempt("/api/bookings")


async def test_probing_health_in_a_tight_loop_never_429s(client, health_db, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    codes = {(await client.get("/api/health/live")).status_code for _ in range(250)}

    assert codes == {200}
