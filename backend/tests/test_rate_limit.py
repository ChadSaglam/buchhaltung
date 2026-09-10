"""Rate limiting (B-07): per-tenant buckets for logged-in traffic, per-IP otherwise,
and a 429 that uses the uniform error envelope."""

from __future__ import annotations

from datetime import timedelta

import pytest
from starlette.requests import Request

from app.core.config import settings
from app.core.rate_limit import tenant_or_ip
from app.core.security import create_access_token
from tests.factories import auth_headers, create_tenant, create_user
from tests.test_tenant_isolation import TwoTenants, tenants  # noqa: F401  (fixture re-export)


def _request(headers: dict[str, str] | None = None, ip: str = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (ip, 12345),
    }
    return Request(scope)


# ── key function ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_key_is_tenant_for_valid_token(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    assert tenant_or_ip(_request(auth_headers(user))) == f"tenant:{tenant.id}"


def test_key_is_ip_without_token():
    assert tenant_or_ip(_request(ip="192.0.2.7")) == "ip:192.0.2.7"


def test_key_is_ip_for_invalid_or_expired_token():
    assert tenant_or_ip(_request({"Authorization": "Bearer not-a-jwt"})) == "ip:10.0.0.1"
    expired = create_access_token({"sub": "1", "tid": 1}, expires_delta=timedelta(minutes=-1))
    assert tenant_or_ip(_request({"Authorization": f"Bearer {expired}"})) == "ip:10.0.0.1"


def test_key_accepts_legacy_tenant_id_claim():
    token = create_access_token({"sub": "1", "tenant_id": 42})
    assert tenant_or_ip(_request({"Authorization": f"Bearer {token}"})) == "tenant:42"


def test_key_ignores_token_without_tenant_claim():
    token = create_access_token({"sub": "1"})
    assert tenant_or_ip(_request({"Authorization": f"Bearer {token}"})) == "ip:10.0.0.1"


# ── end to end ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenants_on_the_same_ip_have_separate_buckets(client, monkeypatch, tenants: TwoTenants):  # noqa: F811
    monkeypatch.setattr(settings, "RATE_LIMIT_CLASSIFY", "2/minute")
    body = {"beschreibung": "Migros Einkauf", "betrag": 10.0}

    for _ in range(2):
        resp = await client.post("/api/classify/predict", json=body, headers=tenants.headers_a)
        assert resp.status_code == 200, resp.text
    resp = await client.post("/api/classify/predict", json=body, headers=tenants.headers_a)
    assert resp.status_code == 429

    # Same client IP, other tenant: untouched bucket.
    resp = await client.post("/api/classify/predict", json=body, headers=tenants.headers_b)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_429_uses_error_envelope(client, monkeypatch, tenants: TwoTenants):  # noqa: F811
    monkeypatch.setattr(settings, "RATE_LIMIT_CLASSIFY", "1/minute")
    body = {"beschreibung": "Migros Einkauf", "betrag": 10.0}

    await client.post("/api/classify/predict", json=body, headers=tenants.headers_a)
    resp = await client.post("/api/classify/predict", json=body, headers=tenants.headers_a)

    assert resp.status_code == 429
    err = resp.json()["error"]
    assert err["code"] == "rate_limited"
    assert err["request_id"] == resp.headers["X-Request-ID"]
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_heavy_limit_applies_to_pdf_parse(client, monkeypatch, tenants: TwoTenants):  # noqa: F811
    monkeypatch.setattr(settings, "RATE_LIMIT_HEAVY", "1/minute")
    files = {"file": ("x.txt", b"not a pdf", "text/plain")}

    # First call is admitted (and rejected by validation), the second is throttled
    # before any parsing happens.
    resp = await client.post("/api/pdf/parse", files=files, headers=tenants.headers_a)
    assert resp.status_code == 400
    resp = await client.post("/api/pdf/parse", files=files, headers=tenants.headers_a)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_anonymous_auth_routes_are_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", "1/minute")
    body = {"email": "nobody@example.ch", "password": "wrong-password"}

    resp = await client.post("/api/auth/login", json=body)
    assert resp.status_code in (400, 401)
    resp = await client.post("/api/auth/login", json=body)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"
