from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
        "version": "2.0.0",
        "checks": checks,
    }