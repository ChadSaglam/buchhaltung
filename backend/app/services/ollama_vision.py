"""Ollama vision integration for invoice/receipt scanning."""
from __future__ import annotations
import asyncio
import base64
import json
import logging
import re
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

INVOICE_PROMPT = """You are an expert Swiss receipt/invoice reader. Analyze this image carefully and extract ALL information.
Extract these fields as JSON:
- vendor: The COMPANY/STORE NAME at the TOP (e.g. Migros, Coop, Landi). NOT a date.
- date: Transaction DATE in DD.MM.YYYY format
- invoice_number: Receipt/invoice number (Bon, Rechnung-Nr, Beleg, Trx-Id)
- total_amount: TOTAL CHF amount. Use dot as decimal (58.48 not 58,48)
- net_amount: Net amount before VAT (0 if not visible)
- vat_amount: VAT/MwSt CHF amount (0 if not visible)
- vat_rate: VAT percentage (Swiss: 8.1 or 2.6). 0 if not visible
- description: What was bought (read article/item lines)
- line_items: Array of {item, amount} for individual items if readable
Respond with ONLY valid JSON. No markdown, no explanation."""

INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": "string"},
        "date": {"type": "string"},
        "invoice_number": {"type": "string"},
        "total_amount": {"type": "number"},
        "net_amount": {"type": "number"},
        "vat_amount": {"type": "number"},
        "vat_rate": {"type": "number"},
        "description": {"type": "string"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "amount": {"type": "number"},
                },
            },
        },
    },
    "required": ["vendor", "date", "total_amount", "description"],
}

_CACHE_TTL = 60

KNOWN_VISION_FAMILIES = [
    "gemma3", "llava", "llava-llama3", "llava-phi3", "bakllava",
    "moondream", "minicpm-v", "llava-v1.6", "kimi-k2.5",
    "cogvlm2", "internvl2",
]

# Keyed by (tenant_id, base_url) — prevents cross-tenant cache bleed
_VISION_STATUS_CACHE: dict[tuple[str, str], dict[str, Any]] = {}

def _get_ollama_url() -> str:
    return settings.OLLAMA_BASE_URL.rstrip("/")

def _cache_key(tenant_id: str | None, base_url: str) -> tuple[str, str]:
    return (str(tenant_id or "_global"), base_url)

def _get_cache(tenant_id: str | None, base_url: str) -> dict[str, Any]:
    key = _cache_key(tenant_id, base_url)
    if key not in _VISION_STATUS_CACHE:
        _VISION_STATUS_CACHE[key] = {"data": None, "ts": 0.0}
    return _VISION_STATUS_CACHE[key]

def clear_vision_status_cache(tenant_id: str | None = None) -> None:
    """Invalidate cached Ollama status for one tenant, or all tenants."""
    if tenant_id is None:
        _VISION_STATUS_CACHE.clear()
        return
    for key in [k for k in _VISION_STATUS_CACHE if k[0] == str(tenant_id)]:
        _VISION_STATUS_CACHE.pop(key, None)

async def check_ollama_status_async(tenant_id: str | None = None) -> dict:
    base_url = _get_ollama_url()
    cache = _get_cache(tenant_id, base_url)
    now = time.monotonic()
    if cache["data"] is not None and (now - cache["ts"]) < _CACHE_TTL:
        return cache["data"]
    result = await _check_ollama_status_impl(base_url)
    cache["data"] = result
    cache["ts"] = now
    return result

def check_ollama_status(tenant_id: str | None = None) -> dict:
    """Sync shim — prefer check_ollama_status_async() in async contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _check_ollama_status_impl(_get_ollama_url()))
                return future.result(timeout=15)
        return loop.run_until_complete(_check_ollama_status_impl(_get_ollama_url()))
    except Exception as e:
        return {"ok": False, "error": str(e)}
    
def _is_known_vision(name: str) -> bool:
    base = name.split(":")[0].lower()
    return any(base.startswith(family) for family in KNOWN_VISION_FAMILIES)

async def _check_vision_capability(client: httpx.AsyncClient, base_url: str, name: str) -> str | None:
    if _is_known_vision(name):
        return name
    try:
        r = await client.post(f"{base_url}/api/show", json={"name": name}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            caps = data.get("capabilities", [])
            if any("vision" in c.lower() for c in caps):
                return name
            model_info = data.get("model_info", {})
            if any("vision" in str(v).lower() for v in model_info.values()):
                return name
    except Exception:
        pass
    return None

async def _check_ollama_status_impl(base_url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code != 200:
                return {"ok": False, "error": "Ollama antwortet nicht."}
            models = resp.json().get("models", [])
            if not models:
                return {"ok": False, "error": "Keine Modelle installiert."}

            model_names = [m["name"] for m in models]

            async with httpx.AsyncClient(timeout=10) as vision_client:
                tasks = [_check_vision_capability(vision_client, base_url, n) for n in model_names]
                results = await asyncio.gather(*tasks)

            vision_names = [n for n in results if n]
            vision_names.sort(key=lambda n: (1 if _is_cloud_model(n) else 0))

            return {
                "ok": True,
                "models": model_names,
                "vision_models": vision_names,
                "best_vision": vision_names[0] if vision_names else None,
            }
    except httpx.ConnectError:
        return {"ok": False, "error": "Ollama nicht erreichbar. `ollama serve` starten."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _is_cloud_model(name: str) -> bool:
    return name.endswith(":cloud") or name.endswith("-cloud")

def _validate_and_fix(data: dict) -> dict:
    if not data:
        return data
    vendor = str(data.get("vendor", ""))
    if re.match(r"\d{2}.\d{2}.\d{2,4}", vendor):
        data["vendor"] = ""
    total = data.get("total_amount", 0)
    try:
        total = float(total)
    except (ValueError, TypeError):
        total = 0
    if total > 50000:
        data["total_amount"] = 0
    vat = data.get("vat_rate", 0)
    try:
        vat = float(vat)
    except (ValueError, TypeError):
        vat = 0
    valid_rates = [0, 2.5, 2.6, 3.7, 3.8, 7.7, 8.1]
    if vat > 0:
        closest = min(valid_rates, key=lambda r: abs(r - vat))
        data["vat_rate"] = closest if abs(vat - closest) < 1.0 else 0
    return data

def parse_invoice_text(text: str) -> dict | None:
    """Parse raw OCR text into the invoice dict shape (no LLM)."""
    if not text or not text.strip():
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    date = ""
    for d, mo, y in re.findall(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b", text):
        day, month, year = int(d), int(mo), len(y) == 2 and int(f"20{y}") or int(y)
        if 1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2100:
            date = f"{day:02d}.{month:02d}.{year}"
            break
    invoice_number = ""
    inv_match = re.search(
        r"(?:Bon|Beleg|Rechnung(?:s)?[- ]?Nr\.?|Trx[- ]?Id|Quittung)[^\dA-Za-z]*([A-Za-z0-9\-]+)",
        text, re.IGNORECASE,
    )
    if inv_match:
        invoice_number = inv_match.group(1)

    def _to_float(raw: str) -> float:
        raw = raw.replace("'", "").replace(" ", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return 0.0

    amount_re = r"(\d[\d'' ]*[.,]\d{2})"
    total_amount = 0.0
    for keyword in ("total", "summe", "betrag", "zu zahlen", "gesamt"):
        for ln in lines:
            if keyword in ln.lower():
                m = re.findall(amount_re, ln)
                if m:
                    total_amount = _to_float(m[-1])
                    break
        if total_amount:
            break
    if not total_amount:
        all_amounts = [_to_float(m) for m in re.findall(amount_re, text)]
        if all_amounts:
            total_amount = max(all_amounts)
    vat_rate = 0.0
    vat_match = re.search(r"(\d{1,2}[.,]\d)\s*%", text)
    if vat_match:
        vat_rate = _to_float(vat_match.group(1))
    vendor = ""
    for ln in lines:
        if re.fullmatch(r"[\d\W]+", ln):
            continue
        if re.search(r"\d{2}[.\-/]\d{2}", ln):
            continue
        vendor = ln[:80]
        break
    if not vendor and total_amount == 0:
        return None
    data = {
        "vendor": vendor, "date": date, "invoice_number": invoice_number,
        "total_amount": total_amount, "net_amount": 0, "vat_amount": 0,
        "vat_rate": vat_rate, "description": " ".join(lines[:3])[:200], "line_items": [],
    }
    return _validate_and_fix(data)

def _parse_json_response(content: str) -> dict | None:
    if not content or not content.strip():
        return None
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(cleaned[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass
    return None

async def extract_invoice_async(image_bytes: bytes, model: str) -> dict | None:
    base_url = _get_ollama_url()
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    is_cloud = _is_cloud_model(model)
    formats = ["plain"] if is_cloud else ["schema", "plain"]
    timeout = 60 if is_cloud else 120

    async with httpx.AsyncClient(timeout=timeout) as client:
        for use_format in formats:
            payload: dict = {
                "model": model,
                "messages": [{"role": "user", "content": INVOICE_PROMPT, "images": [img_b64]}],
                "stream": False,
            }
            if not is_cloud:
                payload["options"] = {"temperature": 0}
            if use_format == "schema" and not is_cloud:
                payload["format"] = INVOICE_SCHEMA
            try:
                logger.info(f"[VISION] {model} attempting ({use_format}, timeout={timeout}s)")
                resp = await client.post(f"{base_url}/api/chat", json=payload)
                if resp.status_code != 200:
                    logger.warning(f"[VISION] {model} returned {resp.status_code}: {resp.text[:200]}")
                    continue
                resp_json = resp.json()
                content = resp_json.get("message", {}).get("content", "")
                thinking = resp_json.get("message", {}).get("thinking", "")
                data = _parse_json_response(content)
                if not data and thinking:
                    data = _parse_json_response(thinking)
                if data and isinstance(data, dict):
                    has_vendor = bool(data.get("vendor", ""))
                    has_total = data.get("total_amount", 0) not in (0, None, "")
                    if has_vendor or has_total:
                        logger.info(f"[VISION] {model} success: vendor={data.get('vendor')}")
                        return _validate_and_fix(data)
                    else:
                        logger.warning(f"[VISION] {model} parsed but no vendor/total. content={content[:300]}")
                else:
                    logger.warning(f"[VISION] {model} no JSON. content={content[:300]}")
            except httpx.TimeoutException:
                logger.warning(f"[VISION] {model} timed out after {timeout}s")
                continue
            except Exception as e:
                logger.warning(f"[VISION] {model} exception: {e}")
                continue
    return None


def extract_invoice(image_bytes: bytes, model: str) -> dict | None:
    """Sync shim retained for backwards-compatible callers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, extract_invoice_async(image_bytes, model))
                return future.result(timeout=130)
        return loop.run_until_complete(extract_invoice_async(image_bytes, model))
    except Exception as e:
        logger.warning(f"[VISION] sync shim error: {e}")
        return None


async def extract_invoice_with_pipeline_async(
    image_bytes: bytes, vision_model_names: list[str],
) -> tuple[dict | None, dict]:
    pipeline_info: dict = {"pipeline": "buchhaltung", "steps": []}
    PREFERRED = ["gemma3:12b", "gemma3:4b", "kimi-k2.5:cloud"]
    ranked = [m for m in PREFERRED if m in vision_model_names] or vision_model_names[:1]
    if not ranked:
        pipeline_info["error"] = "Kein Vision-Modell verfügbar"
        return None, pipeline_info
    data = None
    vision_model = None
    for i, model_name in enumerate(ranked):
        model_type = "Cloud" if _is_cloud_model(model_name) else "Lokal"
        pipeline_info["steps"].append(f"Versuch {i + 1}: {model_name} ({model_type})")
        data = await extract_invoice_async(image_bytes, model_name)
        if data:
            vision_model = model_name
            pipeline_info["steps"].append(f"✅ Rechnung erkannt mit {model_name}")
            break
        else:
            pipeline_info["steps"].append(f"❌ {model_name} fehlgeschlagen")
    if not data or not vision_model:
        pipeline_info["error"] = f"Alle Vision-Modelle fehlgeschlagen: {', '.join(ranked)}"
        return None, pipeline_info
    pipeline_info["vision_model"] = vision_model
    pipeline_info["vision_data"] = data.copy()
    return data, pipeline_info


def extract_invoice_with_pipeline(
    image_bytes: bytes, vision_model_names: list[str],
) -> tuple[dict | None, dict]:
    """Sync shim retained for backwards compatibility."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, extract_invoice_with_pipeline_async(image_bytes, vision_model_names))
                return future.result(timeout=400)
        return loop.run_until_complete(extract_invoice_with_pipeline_async(image_bytes, vision_model_names))
    except Exception as e:
        logger.warning(f"[VISION] pipeline sync shim error: {e}")
        return None, {"error": str(e)}