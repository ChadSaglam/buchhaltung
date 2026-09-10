"""Rate limiting — keyed per tenant for logged-in traffic, per IP otherwise.

Two layers:

* `enforce_default_limit` is an app-level dependency (see `main.py`) that
  applies `RATE_LIMIT_DEFAULT` to every route. It runs before
  `get_current_user`, so the tenant comes from decoding the Bearer token
  without a DB round-trip; a forged token falls back to the IP bucket and is
  rejected by `get_current_user` right after. slowapi's own middleware is not
  used: it resolves the handler from `app.routes`, which FastAPI >= 0.135
  nests per included router, so it silently skipped every route.
* `@limiter.limit(...)` on the expensive routes (`scanner/extract`, `classify*`,
  `ai/*`, `pdf/parse`) replaces the default with a tighter per-tenant bucket.

Limits live in `core/config.py` (`RATE_LIMIT_*`) and are read per request so
they can be tuned per environment without code changes.
"""

from __future__ import annotations

import math
import time

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import decode_access_token


def tenant_id_from_token(request: Request) -> int | None:
    """`tid` from a valid Bearer token, without a DB round-trip. None when absent/invalid."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    payload = decode_access_token(token.strip())
    if not payload:
        return None
    # `tid` is the platform claim; `tenant_id` is the pre-contract name (see core/deps.py).
    tid = payload.get("tid", payload.get("tenant_id"))
    try:
        return int(tid) if tid is not None else None
    except (TypeError, ValueError):
        return None


def tenant_or_ip(request: Request) -> str:
    """Rate-limit key: `tenant:<id>` for authenticated calls, `ip:<addr>` for the rest."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        tenant_id = tenant_id_from_token(request)
    if tenant_id is not None:
        return f"tenant:{tenant_id}"
    return f"ip:{get_remote_address(request)}"


# Callables so the current settings value is used on every request.
def default_limit() -> str:
    return settings.RATE_LIMIT_DEFAULT


def classify_limit() -> str:
    return settings.RATE_LIMIT_CLASSIFY


def heavy_limit() -> str:
    return settings.RATE_LIMIT_HEAVY


limiter = Limiter(key_func=tenant_or_ip, default_limits=[default_limit])


async def enforce_default_limit(request: Request) -> None:
    """App-level dependency: apply the default limit unless the route carries its own."""
    # `endpoint` is put into the scope by the router once the route is matched;
    # slowapi uses it to skip routes that are decorated with their own limit.
    limiter._check_request_limit(request, request.scope.get("endpoint"), in_middleware=True)


def retry_after_seconds(request: Request) -> int | None:
    """Seconds until the bucket that produced the current 429 resets."""
    current = getattr(request.state, "view_rate_limit", None)
    if not current:
        return None
    reset_at, _remaining = limiter.limiter.get_window_stats(current[0], *current[1])
    return max(1, math.ceil(reset_at - time.time()))
