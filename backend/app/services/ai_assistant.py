"""AI assistant service.

Talks to the tenant's Ollama instance (the same one the scanner uses) to answer
bookkeeping questions grounded in the tenant's real data. Model + base URL are
resolved from ScannerConfig with a safe fallback to global settings and, if
needed, the first text-capable model reported by ``/api/tags``.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking
from app.models.kontenplan import Konto
from app.services.scanner_config import ScannerConfigService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Du bist der AI-Assistent einer Schweizer Buchhaltungs-App. "
    "Beantworte Fragen zu Buchungen, Konten (Kontenplan), MwSt/VAT und Auswertungen "
    "präzise und knapp auf Deutsch. Du erhältst einen kompakten Kontext mit echten, "
    "aggregierten Buchungsdaten und dem Kontenplan des Mandanten (als JSON). "
    "Nutze ausschliesslich diesen Kontext für konkrete Zahlen und Kontonummern. "
    "Erfinde keine Beträge. Wenn Daten fehlen, sage das ehrlich und verweise auf die "
    "passende Seite (Kontoauszug, Scanner, Modell, Insights). "
    "Formatiere Beträge als CHF mit zwei Nachkommastellen."
)


async def resolve_ollama(tenant_id: int, db: AsyncSession) -> tuple[str, str]:
    """Return (base_url, model) for this tenant, with robust fallbacks."""
    base_url = settings.OLLAMA_BASE_URL
    model: str | None = None
    try:
        cfg = await ScannerConfigService(tenant_id, db).get_or_create()
        if cfg.ollama_base_url:
            base_url = cfg.ollama_base_url
        model = cfg.default_ollama_model
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[AI] could not load ScannerConfig: %s", exc)

    base_url = (base_url or "http://localhost:11434").rstrip("/")

    if not model:
        # Ask Ollama which models exist and prefer a non-vision text model.
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    names = [m.get("name", "") for m in resp.json().get("models", [])]
                    names = [n for n in names if n]
                    if names:
                        # Prefer common instruct/text models if present.
                        preferred = next(
                            (n for n in names if any(k in n.lower() for k in ("llama", "qwen", "mistral", "gemma", "phi"))),
                            names[0],
                        )
                        model = preferred
        except Exception as exc:
            logger.warning("[AI] /api/tags lookup failed: %s", exc)

    return base_url, (model or "llama3.1")


async def build_context(tenant_id: int, db: AsyncSession) -> dict[str, Any]:
    """Assemble a compact, token-bounded context from the tenant's data."""
    # Stats
    total_count = await db.scalar(
        select(func.count()).select_from(Booking).where(Booking.tenant_id == tenant_id)
    )
    total_amount = await db.scalar(
        select(func.coalesce(func.sum(Booking.betrag), 0.0)).where(Booking.tenant_id == tenant_id)
    )

    # Recent bookings (bounded)
    rows = (
        (
            await db.execute(
                select(Booking)
                .where(Booking.tenant_id == tenant_id)
                .order_by(Booking.id.desc())
                .limit(60)
            )
        )
        .scalars()
        .all()
    )
    recent = [
        {
            "datum": b.datum,
            "beschreibung": b.beschreibung,
            "betrag": round(float(b.betrag or 0), 2),
            "soll": b.kt_soll,
            "haben": b.kt_haben,
            "mwst": b.mwst_code,
        }
        for b in rows
    ]

    # Monthly aggregation (from the recent slice + a wider sum query)
    monthly: dict[str, dict[str, float]] = {}
    all_rows = (
        (
            await db.execute(
                select(Booking.datum, Booking.betrag).where(Booking.tenant_id == tenant_id)
            )
        )
        .all()
    )
    for datum, betrag in all_rows:
        key = _month_key(datum)
        if not key:
            continue
        m = monthly.setdefault(key, {"einnahmen": 0.0, "ausgaben": 0.0, "anzahl": 0.0})
        amt = float(betrag or 0)
        if amt >= 0:
            m["einnahmen"] += amt
        else:
            m["ausgaben"] += abs(amt)
        m["anzahl"] += 1
    monthly_list = [
        {"monat": k, **{kk: round(vv, 2) for kk, vv in v.items()}}
        for k, v in sorted(monthly.items(), reverse=True)
    ][:6]

    # Account plan (Kontenplan) — helps VAT/account questions
    konten = (
        (
            await db.execute(
                select(Konto).where(Konto.tenant_id == tenant_id).limit(200)
            )
        )
        .scalars()
        .all()
    )
    kontenplan = [{"konto": k.konto_nr, "bezeichnung": k.beschreibung} for k in konten]

    return {
        "stats": {"anzahl_buchungen": int(total_count or 0), "total_chf": round(float(total_amount or 0), 2)},
        "monatlich": monthly_list,
        "kontenplan": kontenplan[:120],
        "letzte_buchungen": recent,
    }


def _month_key(datum: str | None) -> str | None:
    if not datum:
        return None
    s = datum.strip()
    # YYYY-MM-DD
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    # DD.MM.YYYY  or DD/MM/YYYY
    for sep in (".", "/"):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3 and len(parts[2]) == 4:
                return f"{parts[2]}-{parts[1].zfill(2)}"
    return None


def _build_messages(messages: list[dict], context: dict) -> list[dict]:
    ctx = json.dumps(context, ensure_ascii=False)[:8000]
    return [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nKontext (JSON):\n{ctx}"},
        *messages,
    ]


async def stream_chat(
    tenant_id: int, db: AsyncSession, messages: list[dict]
) -> AsyncGenerator[str]:
    """Yield SSE-formatted tokens from Ollama's streaming chat API.

    Emits ``data: {json}\\n\\n`` frames. On failure, emits a single error frame
    so the client can show a precise message instead of a generic fallback.
    """
    base_url, model = await resolve_ollama(tenant_id, db)
    context = await build_context(tenant_id, db)
    payload = {
        "model": model,
        "stream": True,
        "messages": _build_messages(messages, context),
        "options": {"temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=8.0)) as client:
            async with client.stream("POST", f"{base_url}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "ignore")[:200]
                    yield _sse({"error": f"Ollama HTTP {resp.status_code}", "detail": body, "model": model})
                    return
                yield _sse({"start": True, "model": model})
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield _sse({"token": token})
                    if chunk.get("done"):
                        yield _sse({"done": True})
                        return
    except httpx.ConnectError as exc:
        yield _sse({"error": "connect", "detail": f"{base_url}: {exc}", "model": model})
    except httpx.TimeoutException:
        yield _sse({"error": "timeout", "model": model})
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("[AI] stream_chat failed")
        yield _sse({"error": "unknown", "detail": str(exc)[:200]})


async def summarize(tenant_id: int, db: AsyncSession) -> dict:
    """Non-streaming monthly summary. Returns {content} or {error}."""
    base_url, model = await resolve_ollama(tenant_id, db)
    context = await build_context(tenant_id, db)
    prompt = (
        "Fasse die folgende Monatsauswertung einer Schweizer Buchhaltung in 3–5 kurzen "
        "Sätzen auf Deutsch zusammen. Hebe auffällige Ausreisser hervor, bleibe sachlich, "
        "erfinde keine Zahlen.\n\nDaten (JSON):\n"
        + json.dumps(context, ensure_ascii=False)[:6000]
    )
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": "Du bist ein präziser Buchhaltungs-Analyst. Antworte knapp auf Deutsch."},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=8.0)) as client:
            resp = await client.post(f"{base_url}/api/chat", json=payload)
            if resp.status_code != 200:
                return {"error": f"Ollama HTTP {resp.status_code}", "model": model}
            content = resp.json().get("message", {}).get("content", "").strip()
            if not content:
                return {"error": "empty", "model": model}
            return {"content": content, "model": model}
    except httpx.ConnectError as exc:
        return {"error": "connect", "detail": str(exc)[:200], "model": model}
    except httpx.TimeoutException:
        return {"error": "timeout", "model": model}
    except Exception as exc:  # pragma: no cover
        logger.exception("[AI] summarize failed")
        return {"error": "unknown", "detail": str(exc)[:200]}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
