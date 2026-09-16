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
* `RATE_LIMIT_AUTH` on `/auth/register`, `/auth/login` and `/auth/sso` — the
  only unauthenticated write paths, so the bucket is per IP and tight (B-55).

Limits live in `core/config.py` (`RATE_LIMIT_*`) and are read per request so
they can be tuned per environment without code changes.
"""

from __future__ import annotations

import logging
import math
import time

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)


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


def auth_limit() -> str:
    return settings.RATE_LIMIT_AUTH


def storage_uri() -> str:
    """Where the counters live (B-55).

    In-process memory is right for one uvicorn process and quietly wrong for
    two — each worker would grant the full quota. `REDIS_URL` makes the buckets
    shared. A configured URL whose client is not installed is a configuration
    mistake worth saying out loud, not worth crashing over, so it falls back to
    memory with a warning.
    """
    url = (settings.REDIS_URL or "").strip()
    if not url:
        return "memory://"
    try:
        import redis  # noqa: F401
    except ImportError:
        logger.warning("[LIMIT] REDIS_URL is set but the redis client is missing; using in-memory limits")
        return "memory://"
    return url


limiter = Limiter(key_func=tenant_or_ip, default_limits=[default_limit], storage_uri=storage_uri())


#: Paths the default limit never applies to (B-61). A liveness or readiness probe
#: runs every few seconds from every instance and every load balancer; sharing the
#: 200/minute bucket with real traffic means a busy minute answers a probe with 429,
#: and every orchestrator reads 429 as "unhealthy" and takes the instance out.
#: These endpoints do no work worth protecting: `/live` touches nothing, the
#: readiness check is one bounded `SELECT 1`.
EXEMPT_PATHS = ("/api/health",)


def is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in EXEMPT_PATHS)


async def enforce_default_limit(request: Request) -> None:
    """App-level dependency: apply the default limit unless the route carries its own."""
    if is_exempt(request.url.path):
        return
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
