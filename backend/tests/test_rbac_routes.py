"""B-40 — every mutating route carries a role check; the ladder is enforced over HTTP.

`core/deps.py` had `require_editor` / `require_admin` with zero callers, so an
SSO `viewer` could book, retrain, wipe memory or replace the Kontenplan.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.main import app
from tests.factories import auth_headers, create_tenant, create_user

# Unauthenticated by design (login, SSO hand-off, signed platform events).
PUBLIC = {"/api/auth/register", "/api/auth/login", "/api/auth/sso", "/api/platform/events"}
# POST in shape only — they read, they don't write. Every authenticated role may call them.
READ_POSTS = {"/api/ai/chat", "/api/ai/summary", "/api/export/banana", "/api/export/excel", "/api/export/csv"}
# Destructive or tenant-wide configuration: admin and up.
ADMIN = {
    ("PUT", "/api/kontenplan/"),
    ("DELETE", "/api/classify/{action}"),
    ("POST", "/api/classify/upload"),
    ("PUT", "/api/scanner/config"),
    ("PATCH", "/api/scanner/config"),
}


def _minimum_role(dependant) -> str | None:
    role = getattr(dependant.call, "minimum_role", None)
    if role:
        return role
    for sub in dependant.dependencies:
        found = _minimum_role(sub)
        if found:
            return found
    return None


def _mutating_routes():
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        for method in route.methods - {"GET", "HEAD", "OPTIONS"}:
            yield method, route


def test_every_mutating_route_has_a_role_check():
    missing = []
    for method, route in _mutating_routes():
        if route.path in PUBLIC or route.path in READ_POSTS:
            continue
        expected = "admin" if (method, route.path) in ADMIN else "editor"
        if _minimum_role(route.dependant) != expected:
            missing.append(f"{method} {route.path} (want {expected}, got {_minimum_role(route.dependant)})")
    assert not missing, "\n".join(missing)


@pytest.mark.asyncio
async def test_viewer_cannot_write_but_can_read(client, db_session):
    tenant = await create_tenant(db_session)
    viewer = await create_user(db_session, tenant, role="viewer")
    headers = auth_headers(viewer)

    assert (await client.get("/api/bookings/", headers=headers)).status_code == 200
    resp = await client.post("/api/bookings/", json=[], headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Requires editor role or higher"


@pytest.mark.asyncio
async def test_editor_cannot_replace_kontenplan_or_wipe_training_data(client, db_session):
    tenant = await create_tenant(db_session)
    editor = await create_user(db_session, tenant, role="editor")
    headers = auth_headers(editor)

    assert (await client.put("/api/kontenplan/", json={"konten": []}, headers=headers)).status_code == 403
    resp = await client.post(
        "/api/import/banana?replace=true",
        files={"file": ("x.xls", b"not-an-xls", "application/vnd.ms-excel")},
        headers=headers,
    )
    assert resp.status_code == 403
