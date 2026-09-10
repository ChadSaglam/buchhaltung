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
