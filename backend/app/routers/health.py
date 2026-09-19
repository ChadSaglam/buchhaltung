"""Health (B-13, B-61).

Three endpoints, three different questions, and mixing them up is how a database
blip turns into a restart loop:

* ``GET /api/health/live`` — **is this process alive?** No I/O at all, always 200.
  A liveness probe that touches the database restarts every container at once the
  moment the database hiccups, which is the opposite of what it is for.
* ``GET /api/health`` — **should this instance get traffic?** It runs a cheap
  ``SELECT 1`` and answers **503** when it cannot. Until B-61 this answered a flat
  ``{"status": "ok"}`` in production without touching anything, so an instance with
  no database kept taking requests and no load balancer could tell.
* ``GET /api/health/detail`` — for a human debugging. It names upstreams and
  exception types, so in production it is behind an admin login.

All three are exempt from the default rate limit (`core/rate_limit.py`): probes
poll every few seconds, and a 429 reads as "unhealthy" to every orchestrator
there is.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_db
from app.core.deps import ROLE_RANK, get_current_user

router = APIRouter(prefix="/api/health", tags=["health"])

#: A readiness probe must fail fast. A database that hangs has to look like a
#: database that is down, or the probe hangs with it and the orchestrator learns
#: nothing until its own timeout.
DB_TIMEOUT_SECONDS = 2.0

#: Which checks decide whether this instance is healthy. Everything else is
#: reported and ignored.
PFLICHT_CHECKS = ("database",)


async def _database_status() -> tuple[str, str | None]:
    """("ok"|"error", applied Alembic revision or None when the table does not exist)."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            try:
                revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            except SQLAlchemyError:
                # Dev/test databases built by create_all carry no alembic_version table.
                await session.rollback()
                revision = None
        return "ok", revision
    except Exception:
        return "error", None


async def _database_reachable() -> bool:
    """One ``SELECT 1``, bounded. Cheaper than `_database_status`: no second query,
    no revision lookup — this runs on every probe of every instance."""
    try:
        async with asyncio.timeout(DB_TIMEOUT_SECONDS):
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _worker_mode() -> str:
    return "in-api" if settings.RUN_WORKER_IN_API else "separate"


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness (B-61). The process answered, therefore it is alive.

    Deliberately does nothing else. Kubernetes restarts a container whose liveness
    probe fails; if that probe asked the database, one database restart would take
    down every instance at the same moment.
    """
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("")
async def health(response: Response) -> dict[str, Any]:
    """Readiness (B-13, B-61). **503 when this instance should not get traffic.**

    Production still answers with status and version only — everything else is an
    internal detail — but it now *checks*, which it did not before.
    """
    if settings.is_production:
        bereit = await _database_reachable()
        if not bereit:
            response.status_code = 503
        return {"status": "ok" if bereit else "degraded", "version": settings.APP_VERSION}

    database, revision = await _database_status()
    if database != "ok":
        response.status_code = 503
    return {
        "status": "ok" if database == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "database": database,
        "migration_head": revision,
        "storage": settings.STORAGE_BACKEND.strip().lower(),
        "worker": _worker_mode(),
    }


async def _check_db() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}


async def _check_ollama() -> dict[str, Any]:
    base_url = getattr(settings, "OLLAMA_BASE_URL", None)
    if not base_url:
        return {"status": "not_configured"}
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            resp.raise_for_status()
        return {"status": "ok", "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}


#: `auto_error=False`: outside production the endpoint is open, so a missing
#: Authorization header must not 403 before the dependency has looked at the
#: environment.
_optional_bearer = HTTPBearer(auto_error=False)


async def _admin_in_production(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Open in development, admin-only in production (B-61).

    Not `Depends(require_admin)` on the route: that would demand a token in
    development too, and this endpoint's whole job there is to be reachable from
    a terminal without one.
    """
    if not settings.is_production:
        return
    if credentials is None:
        raise HTTPException(status_code=401, detail="Nicht angemeldet.")
    user = await get_current_user(request, credentials, db)
    if ROLE_RANK.get(user.role, -1) < ROLE_RANK["admin"]:
        raise HTTPException(status_code=403, detail="Requires admin role or higher")


@router.get("/detail", dependencies=[Depends(_admin_in_production)])
async def health_detail(response: Response) -> dict[str, Any]:
    """For a human, not for a probe (B-61).

    It names the upstream and the exception class, which is exactly what makes it
    useful and exactly why it is behind an admin login in production.
    """
    checks = {
        "database": await _check_db(),
        "ollama": await _check_ollama(),
    }
    # Only a *required* dependency makes this instance unhealthy. Ollama is
    # optional by design — B-20 put it last in the checklist and marked it so,
    # because a Swiss QR bill is decoded exactly with no model involved. An
    # instance that reports 503 because the optional AI service is asleep would
    # be pulled out of the load balancer for no reason.
    degraded = any(checks[name].get("status") == "error" for name in PFLICHT_CHECKS)
    if degraded:
        response.status_code = 503
    return {
        "status": "degraded" if degraded else "ok",
        "version": settings.APP_VERSION,
        "checks": checks,
    }
