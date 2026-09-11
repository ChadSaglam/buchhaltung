"""SSO hand-off, verifier side (B-36, chadev-platform/contracts/sso.md).

The token helper here mints exactly what billing's `create_sso_token` mints,
so a claim rule that changes on either side shows up as a failing test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from jose import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_access_token
from app.models.kontenplan import Konto
from app.models.sso_nonce import SsoNonce
from app.models.tenant import Tenant
from app.models.user import PLATFORM_PASSWORD_SENTINEL, User
from tests.factories import create_tenant, create_user

pytestmark = pytest.mark.asyncio

SECRET = "platform-shared-secret-for-tests"

TENANT_SNAPSHOT = {
    "name": "Muster AG",
    "slug": "muster-ag",
    "subscription_plan": "trial",
    "trial_ends_at": "2026-10-11T00:00:00Z",
}


def mint(**overrides) -> str:
    """Billing's SSO token, byte-for-byte (`app/api/sso.py::create_sso_token`)."""
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": "billing",
        "aud": "buchhaltung",
        "type": "sso",
        "sub": "42",
        "email": "anna@example.ch",
        "name": "Anna Muster",
        "tid": 7,
        "role": "admin",
        "tenant": dict(TENANT_SNAPSHOT),
        "iat": now,
        "exp": now + 120,
        "jti": uuid4().hex,
    }
    secret = overrides.pop("secret", SECRET)
    payload.update(overrides)
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def platform_secret(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_SHARED_SECRET", SECRET)


async def sso(client, token: str):
    return await client.post("/api/auth/sso", json={"token": token})


async def test_unset_secret_hides_the_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_SHARED_SECRET", None)
    resp = await sso(client, mint())
    assert resp.status_code == 404


async def test_first_hop_mirrors_tenant_and_shadow_user(client, db_session, platform_secret):
    resp = await sso(client, mint())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"

    tenant = await db_session.scalar(select(Tenant).where(Tenant.platform_tenant_id == 7))
    assert tenant is not None
    assert tenant.name == "Muster AG"
    assert tenant.slug == "muster-ag"
    assert tenant.subscription_plan == "trial"
    assert tenant.trial_ends_at is not None and tenant.trial_ends_at.year == 2026
    assert tenant.is_active is True
    # A mirrored tenant gets its Kontenplan like a registered one.
    assert await db_session.scalar(select(Konto.id).where(Konto.tenant_id == tenant.id).limit(1)) is not None

    user = await db_session.scalar(select(User).where(User.platform_user_id == "42"))
    assert user is not None
    assert user.tenant_id == tenant.id
    assert user.email == "anna@example.ch"
    assert user.display_name == "Anna Muster"
    assert user.role == "admin"
    assert user.auth_source == "platform"
    assert user.password_hash == PLATFORM_PASSWORD_SENTINEL

    # Same session shape as /api/auth/login: {sub, tid, role, type, jti}.
    claims = decode_access_token(body["access_token"])
    assert claims["sub"] == str(user.id)
    assert claims["tid"] == tenant.id
    assert claims["role"] == "admin"
    assert claims["type"] == "access"

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["tenant_name"] == "Muster AG"


async def test_second_hop_reuses_and_refreshes(client, db_session, platform_secret):
    first = await sso(client, mint())
    assert first.status_code == 200
    second = await sso(
        client,
        mint(
            email="anna.neu@example.ch",
            name="Anna Neu",
            role="editor",
            tenant={**TENANT_SNAPSHOT, "name": "Muster Neu AG", "subscription_plan": "pro", "trial_ends_at": None},
        ),
    )
    assert second.status_code == 200, second.text

    tenants = (await db_session.execute(select(Tenant).where(Tenant.platform_tenant_id == 7))).scalars().all()
    assert len(tenants) == 1
    tenant = tenants[0]
    assert tenant.name == "Muster Neu AG"
    assert tenant.subscription_plan == "pro"
    assert tenant.trial_ends_at is None
    assert tenant.slug == "muster-ag"  # slug is not renamed

    users = (await db_session.execute(select(User).where(User.tenant_id == tenant.id))).scalars().all()
    assert len(users) == 1
    assert users[0].email == "anna.neu@example.ch"
    assert users[0].display_name == "Anna Neu"
    assert users[0].role == "editor"


async def test_replayed_token_is_rejected(client, db_session, platform_secret):
    token = mint()
    assert (await sso(client, token)).status_code == 200
    resp = await sso(client, token)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_replayed"
    assert await db_session.scalar(select(SsoNonce).limit(1)) is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "billing"},
        {"iss": "buchhaltung"},
        {"type": "access"},
        {"secret": "some-other-secret"},
        {"jti": ""},
        {"tid": "7"},
    ],
    ids=["aud", "iss", "type", "signature", "jti", "tid-type"],
)
async def test_wrong_claims_are_invalid(client, platform_secret, overrides):
    resp = await sso(client, mint(**overrides))
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "sso_invalid"


async def test_expired_token_is_rejected(client, platform_secret):
    now = int(datetime.now(UTC).timestamp())
    resp = await sso(client, mint(iat=now - 300, exp=now - 180))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_expired"


async def test_lifetime_over_120s_is_invalid(client, platform_secret):
    now = int(datetime.now(UTC).timestamp())
    resp = await sso(client, mint(iat=now, exp=now + 121))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_invalid"


async def test_garbage_token_is_invalid(client, platform_secret):
    resp = await sso(client, "not-a-jwt")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "sso_invalid"


async def test_shadow_user_cannot_login_locally(client, platform_secret):
    assert (await sso(client, mint())).status_code == 200
    resp = await client.post("/api/auth/login", json={"email": "anna@example.ch", "password": "!platform"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "platform_user"


async def test_email_of_local_user_in_other_tenant_is_refused(client, db_session, platform_secret):
    other = await create_tenant(db_session)
    await create_user(db_session, other, email="anna@example.ch")
    resp = await sso(client, mint())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken_locally"
    # Nothing was mirrored.
    assert await db_session.scalar(select(Tenant).where(Tenant.platform_tenant_id == 7)) is None


async def test_local_user_of_the_same_tenant_is_linked(client, db_session, platform_secret):
    mirrored = await create_tenant(db_session, name="Muster AG")
    mirrored.platform_tenant_id = 7
    await db_session.commit()
    local = await create_user(db_session, mirrored, email="anna@example.ch", password="Local123!", role="owner")

    resp = await sso(client, mint())
    assert resp.status_code == 200, resp.text
    await db_session.refresh(local)
    assert local.platform_user_id == "42"
    assert local.auth_source == "local"
    assert local.role == "owner"  # a linked local account keeps its own role
    assert decode_access_token(resp.json()["access_token"])["sub"] == str(local.id)

    # ... and can still log in with its password.
    login = await client.post("/api/auth/login", json={"email": "anna@example.ch", "password": "Local123!"})
    assert login.status_code == 200


async def test_unknown_role_degrades_to_viewer(client, db_session, platform_secret):
    assert (await sso(client, mint(role="superuser"))).status_code == 200
    user = await db_session.scalar(select(User).where(User.platform_user_id == "42"))
    assert user.role == "viewer"


async def test_mirrored_tenant_is_isolated_from_others(client, db_session, platform_secret):
    """A second billing tenant with the same name lands in its own tenant with its own slug."""
    a = await sso(client, mint())
    b = await sso(client, mint(sub="99", tid=8, email="beat@example.ch"))
    assert a.status_code == 200 and b.status_code == 200
    tenants = (await db_session.execute(select(Tenant).where(Tenant.platform_tenant_id.in_([7, 8])))).scalars().all()
    assert len(tenants) == 2
    assert len({t.slug for t in tenants}) == 2
    assert decode_access_token(a.json()["access_token"])["tid"] != decode_access_token(b.json()["access_token"])["tid"]
