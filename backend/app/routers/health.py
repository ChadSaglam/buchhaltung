from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import async_session

router = APIRouter(prefix="/api/health", tags=["health"])


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


def _worker_mode() -> str:
    return "in-api" if settings.RUN_WORKER_IN_API else "separate"


@router.get("")
async def health() -> dict[str, Any]:
    """Liveness + deployment facts (B-13).

    Production answers with status and version only; everything else is an
    internal detail that stays inside the perimeter.
    """
    if settings.is_production:
        return {"status": "ok", "version": settings.APP_VERSION}
    database, revision = await _database_status()
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


@router.get("/detail")
async def health_detail() -> dict[str, Any]:
    checks = {
        "database": await _check_db(),
        "ollama": await _check_ollama(),
    }
    degraded = any(c.get("status") == "error" for c in checks.values())
    return {
        "status": "degraded" if degraded else "ok",
        "version": settings.APP_VERSION,
        "checks": checks,
    }
