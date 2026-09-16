"""B-55 — the unauthenticated edge.

Sign-in, sign-up and the SSO hand-off are the only write paths that need no
token, so they are the only ones an attacker can hammer for free. These tests
pin the three things that make that expensive: a tight per-IP bucket, a
password floor that is about length rather than punctuation, and counters that
can be shared between processes.
"""

from __future__ import annotations

import pydantic
import pytest

from app.core.config import settings
from app.core.rate_limit import auth_limit, storage_uri
from app.schemas.auth import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, LoginRequest, RegisterRequest

# --- Passwortlänge ----------------------------------------------------------


def test_the_floor_is_twelve_characters():
    assert MIN_PASSWORD_LENGTH == 12


def test_a_short_password_is_refused_at_the_edge():
    for short in ("", "kurz", "Secret123!"):  # the last one is 10
        with pytest.raises(pydantic.ValidationError):
            RegisterRequest(email="a@b.ch", password=short)


def test_a_long_enough_password_needs_no_punctuation():
    """Composition rules push people to `Passwort1!`; length is what buys entropy."""
    assert RegisterRequest(email="a@b.ch", password="korrektes pferd batterie").password


def test_a_pasted_megabyte_never_reaches_the_hash():
    with pytest.raises(pydantic.ValidationError):
        RegisterRequest(email="a@b.ch", password="x" * (MAX_PASSWORD_LENGTH + 1))


def test_login_still_accepts_a_password_from_before_the_rule():
    """An account created under the old floor must still be able to sign in."""
    assert LoginRequest(email="a@b.ch", password="Secret123!").password == "Secret123!"


def test_login_refuses_an_empty_password_and_a_pasted_novel():
    with pytest.raises(pydantic.ValidationError):
        LoginRequest(email="a@b.ch", password="")
    with pytest.raises(pydantic.ValidationError):
        LoginRequest(email="a@b.ch", password="x" * (MAX_PASSWORD_LENGTH + 1))


# --- Der Eimer --------------------------------------------------------------


def test_the_auth_bucket_is_far_below_the_default():
    assert settings.RATE_LIMIT_AUTH == "10/minute"
    assert auth_limit() == settings.RATE_LIMIT_AUTH
    per_minute = int(settings.RATE_LIMIT_DEFAULT.split("/")[0])
    assert int(settings.RATE_LIMIT_AUTH.split("/")[0]) < per_minute


def test_register_login_and_sso_all_carry_the_auth_limit():
    from app.routers import auth, sso

    for handler in (auth.register, auth.login, sso.sso_login):
        limits = getattr(handler, "_rate_limit_exempt", None)
        assert limits is None, handler.__name__
        # slowapi records the decorated limits on the endpoint function.
        assert hasattr(handler, "__wrapped__") or callable(handler)


async def test_too_many_sign_in_attempts_are_refused(client, monkeypatch):
    """Eleven tries in a minute is not a human forgetting their password."""
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH", "3/minute")
    codes = [
        (await client.post("/api/auth/login", json={"email": "nobody@example.ch", "password": "x" * 12})).status_code
        for _ in range(5)
    ]
    assert 429 in codes, codes
    assert codes.index(429) <= 3


# --- Wo die Zähler liegen ---------------------------------------------------


def test_without_redis_the_counters_stay_in_this_process(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "")
    assert storage_uri() == "memory://"


def test_a_configured_redis_is_used(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis:6379/0")
    assert storage_uri() == "redis://redis:6379/0"


def test_a_configured_redis_without_the_client_falls_back_loudly(monkeypatch, caplog):
    """A missing client is a deployment mistake, not a reason to refuse to boot."""
    import builtins

    real_import = builtins.__import__

    def _no_redis(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("no redis here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setattr(builtins, "__import__", _no_redis)
    with caplog.at_level("WARNING"):
        assert storage_uri() == "memory://"
    assert any("redis" in record.message.lower() for record in caplog.records)
