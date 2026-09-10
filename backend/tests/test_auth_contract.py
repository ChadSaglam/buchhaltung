"""Platform auth contract (chadev-platform/contracts/auth.md).

Token shape {sub, tid, role, type, exp, jti}; legacy `tenant_id` claim still
accepted for one release; role ladder enforced by `require_role`.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_admin, require_editor, require_owner
from app.core.security import ROLES, create_access_token, issue_access_token
from tests.factories import auth_headers, create_tenant, create_user

pytestmark = pytest.mark.asyncio


def _claims(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


async def test_login_token_has_platform_claims(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant, password="Secret123!")
    resp = await client.post("/api/auth/login", json={"email": user.email, "password": "Secret123!"})
    assert resp.status_code == 200
    claims = _claims(resp.json()["access_token"])
    assert claims["sub"] == str(user.id)
    assert claims["tid"] == tenant.id
    assert claims["role"] == "owner"
    assert claims["type"] == "access"
    assert len(claims["jti"]) == 32
    assert "exp" in claims
    assert "tenant_id" not in claims


async def test_register_token_has_platform_claims(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "Secret123!", "tenant_name": "Neu AG"},
    )
    assert resp.status_code in (200, 201)
    claims = _claims(resp.json()["access_token"])
    assert {"sub", "tid", "role", "type", "exp", "jti"} <= set(claims)


async def test_legacy_tenant_id_claim_still_accepted(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    legacy = create_access_token({"sub": str(user.id), "tenant_id": user.tenant_id})
    resp = await client.get("/api/kontenplan/", headers={"Authorization": f"Bearer {legacy}"})
    assert resp.status_code == 200


async def test_tid_mismatch_is_rejected(client, db_session):
    tenant_a = await create_tenant(db_session)
    tenant_b = await create_tenant(db_session)
    user = await create_user(db_session, tenant_a)
    forged = create_access_token({"sub": str(user.id), "tid": tenant_b.id, "type": "access"})
    resp = await client.get("/api/kontenplan/", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


async def test_refresh_type_token_cannot_call_api(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    refresh = create_access_token({"sub": str(user.id), "tid": user.tenant_id, "type": "refresh"})
    resp = await client.get("/api/kontenplan/", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


async def test_issue_access_token_role_is_in_contract_set(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    assert _claims(issue_access_token(user))["role"] in ROLES


@pytest.mark.parametrize(
    ("role", "editor_ok", "admin_ok", "owner_ok"),
    [
        ("viewer", False, False, False),
        ("editor", True, False, False),
        ("admin", True, True, False),
        ("owner", True, True, True),
    ],
)
async def test_require_role_ladder(db_session, role, editor_ok, admin_ok, owner_ok):
    """Mounted on a throwaway app so the ladder is tested without touching real routes."""
    app = FastAPI()

    @app.get("/editor", dependencies=[Depends(require_editor)])
    async def _e():
        return {"ok": True}

    @app.get("/admin", dependencies=[Depends(require_admin)])
    async def _a():
        return {"ok": True}

    @app.get("/owner", dependencies=[Depends(require_owner)])
    async def _o():
        return {"ok": True}

    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant, role=role)
    headers = auth_headers(user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        for path, ok in (("/editor", editor_ok), ("/admin", admin_ok), ("/owner", owner_ok)):
            resp = await ac.get(path, headers=headers)
            assert resp.status_code == (200 if ok else 403), (role, path, resp.text)
