"""Platform tenant contract (chadev-platform/contracts/tenant.md) — B-26.

`tenants` carries `slug`, `subscription_plan`, `trial_ends_at`, `is_active`;
registration derives a unique slug; a deactivated tenant locks its users out;
the Alembic migration is reversible.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.services.tenant_setup import slugify, unique_tenant_slug
from tests.conftest import _IS_SQLITE, TEST_DATABASE_URL
from tests.factories import auth_headers, create_tenant, create_user

BACKEND_DIR = Path(__file__).resolve().parents[1]


# ── slug derivation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Meine Firma", "meine-firma"),
        ("Müller & Söhne AG", "muller-sohne-ag"),
        ("  Café Zürich GmbH ", "cafe-zurich-gmbh"),
        ("Chadev/Platform 2026", "chadev-platform-2026"),
        ("---", "tenant"),
        ("", "tenant"),
        ("日本", "tenant"),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_slugify_respects_max_length():
    assert len(slugify("x" * 500)) == 100


@pytest.mark.asyncio
async def test_unique_tenant_slug_adds_suffix_on_collision(db_session):
    await create_tenant(db_session, name="Alpha AG", slug="alpha-ag")
    slug = await unique_tenant_slug(db_session, "Alpha AG")
    assert slug != "alpha-ag"
    assert slug.startswith("alpha-ag-")
    assert len(slug) == len("alpha-ag-") + 6


@pytest.mark.asyncio
async def test_register_sets_contract_columns(client, db_session):
    first = await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "Secret123!", "tenant_name": "Müller AG"},
    )
    second = await client.post(
        "/api/auth/register",
        json={"email": "b@example.com", "password": "Secret123!", "tenant_name": "Müller AG"},
    )
    assert first.status_code == 201 and second.status_code == 201

    me_a = (await client.get("/api/auth/me", headers=_bearer(first))).json()
    me_b = (await client.get("/api/auth/me", headers=_bearer(second))).json()
    assert me_a["tenant_slug"] == "muller-ag"
    assert me_b["tenant_slug"].startswith("muller-ag-")
    assert me_a["tenant_slug"] != me_b["tenant_slug"]
    assert me_a["subscription_plan"] == "free"
    assert me_a["trial_ends_at"] is None


def _bearer(resp) -> dict[str, str]:
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── inactive tenant gate ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inactive_tenant_is_locked_out(client, db_session):
    tenant = await create_tenant(db_session, is_active=False)
    user = await create_user(db_session, tenant)
    resp = await client.get("/api/auth/me", headers=auth_headers(user))
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Tenant deaktiviert"


@pytest.mark.asyncio
async def test_active_tenant_default(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    assert tenant.is_active is True
    resp = await client.get("/api/auth/me", headers=auth_headers(user))
    assert resp.status_code == 200


# ── migration chain (Postgres only) ──────────────────────────────────────────


@pytest.mark.skipif(_IS_SQLITE, reason="Alembic chain is verified against Postgres only.")
def test_tenant_migration_is_reversible():
    """upgrade head → downgrade one → upgrade head, keeping the existing plan value."""
    sync_url = TEST_DATABASE_URL.replace("+asyncpg", "")
    engine = sa.create_engine(sync_url, isolation_level="AUTOCOMMIT")
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}

    def alembic(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND_DIR, env=env, check=True)

    def columns() -> set[str]:
        return {c["name"] for c in sa.inspect(engine).get_columns("tenants")}

    def reset() -> None:
        with engine.connect() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))

    reset()
    try:
        alembic("upgrade", "73f03c35bbed")
        with engine.begin() as conn:
            conn.execute(sa.text("INSERT INTO tenants (name, plan) VALUES ('Alt AG', 'pro')"))

        alembic("upgrade", "head")
        assert {"slug", "subscription_plan", "trial_ends_at", "is_active"} <= columns()
        assert "plan" not in columns()
        with engine.connect() as conn:
            row = conn.execute(sa.text("SELECT slug, subscription_plan, trial_ends_at, is_active FROM tenants")).one()
        assert row == (None, "pro", None, True)

        alembic("downgrade", "-1")
        assert "plan" in columns()
        assert not {"slug", "subscription_plan", "trial_ends_at", "is_active"} & columns()
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT plan FROM tenants")).scalar_one() == "pro"

        alembic("upgrade", "head")
        assert "subscription_plan" in columns()
    finally:
        reset()
        engine.dispose()
