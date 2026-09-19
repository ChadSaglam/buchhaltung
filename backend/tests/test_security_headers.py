"""B-108: the two findings from the 2026-09-19 scan that were real.

The scan reported 44 issues and 42 of them were false — bcrypt read as insecure
hashing, `options={...}` on a verified `jwt.decode` read as "no verify", test
fixtures read as leaked secrets. What it got right was that no response carried
a security header. It also reported `csrf.absent`, which is wrong on its own
terms (Bearer token, no cookie) but points at the same risk from the other side:
a token in localStorage plus no CSP means one XSS takes the session.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_every_response_carries_the_headers(client):
    res = await client.get("/api/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in res.headers["Content-Security-Policy"]


async def test_the_csp_forbids_framing_and_form_posts():
    from app.core.security_headers import CSP

    assert "frame-ancestors 'none'" in CSP
    assert "form-action 'none'" in CSP
    assert "base-uri 'none'" in CSP
    # No script source at all: the API serves JSON and generated documents.
    assert "script-src" not in CSP


async def test_an_error_response_carries_them_too(client):
    """The middleware sits innermost, so responses built by the error handlers
    above it still leave through here. A 404 is as good a test as a 200."""
    res = await client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.headers["X-Content-Type-Options"] == "nosniff"


async def test_hsts_is_not_sent_over_plain_http(client):
    """Pinning localhost to HTTPS in a developer's browser for a year is a
    genuinely unpleasant thing to debug, and the spec ignores it anyway."""
    res = await client.get("/api/health")
    assert "Strict-Transport-Security" not in res.headers


async def test_hsts_is_sent_behind_a_tls_proxy(client):
    res = await client.get("/api/health", headers={"x-forwarded-proto": "https"})
    assert res.headers["Strict-Transport-Security"].startswith("max-age=31536000")
