"""Ollama vision integration for invoice/receipt scanning."""
from __future__ import annotations
import base64
import json
import logging
import re
import time
import concurrent.futures
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"

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

_status_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 60

def check_ollama_status() -> dict:
    now = time.time()
    if _status_cache["data"] and (now - _status_cache["ts"]) < _CACHE_TTL:
        return _status_cache["data"]
    result = _check_ollama_status_impl()
    _status_cache["data"] = result
    _status_cache["ts"] = now
    return result

def _check_ollama_status_impl() -> dict:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return {"ok": False, "error": "Ollama antwortet nicht."}
        models = resp.json().get("models", [])
        if not models:
            return {"ok": False, "error": "Keine Modelle installiert."}

        def check_vision(name: str) -> str | None:
            try:
                r = requests.post(f"{OLLAMA_URL}/api/show", json={"name": name}, timeout=10)
                if r.status_code == 200:
                    caps = r.json().get("capabilities", [])
                    if any("vision" in c.lower() for c in caps):
                        return name
            except Exception:
                pass
            return None

        model_names = [m["name"] for m in models]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results = pool.map(check_vision, model_names)
        vision_names = [n for n in results if n]

        return {
            "ok": True,
            "models": model_names,
            "vision_models": vision_names,
            "best_vision": vision_names[0] if vision_names else None,
        }
    except requests.ConnectionError:
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

def _parse_json_response(content: str) -> dict | None:
    if not content or not content.strip():
        return None
    # Strip markdown code fences
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]  # remove first line
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
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

def extract_invoice(image_bytes: bytes, model: str) -> dict | None:
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    is_cloud = _is_cloud_model(model)
    formats = ["plain"] if is_cloud else ["schema", "plain"]
    timeout = 30 if is_cloud else 60

    for use_format in formats:
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "user", "content": INVOICE_PROMPT, "images": [img_b64]}
            ],
            "stream": False,
        }
        if not is_cloud:
            payload["options"] = {"temperature": 0}
        if use_format == "schema" and not is_cloud:
            payload["format"] = INVOICE_SCHEMA

        try:
            logger.info(f"[VISION] {model} attempting ({use_format}, timeout={timeout}s)")
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout
            )
            if resp.status_code != 200:
                logger.warning(f"[VISION] {model} returned {resp.status_code}: {resp.text[:200]}")
                continue

            resp_json = resp.json()
            # Try main content first, then fall back to thinking field
            content = resp_json.get("message", {}).get("content", "")
            thinking = resp_json.get("message", {}).get("thinking", "")

            # Some cloud models put the JSON in thinking or mix it
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

        except requests.Timeout:
            logger.warning(f"[VISION] {model} timed out after {timeout}s")
            continue
        except Exception as e:
            logger.warning(f"[VISION] {model} exception: {e}")
            continue

    return None


def extract_invoice_with_pipeline(
    image_bytes: bytes, vision_model_names: list[str],
) -> tuple[dict | None, dict]:
    pipeline_info: dict = {"pipeline": "buchhaltung", "steps": []}

    # Force kimi cloud, fallback to gemma3:4b offline only
    PREFERRED = ["kimi-k2.5:cloud", "gemma3:4b"]
    ranked = [m for m in PREFERRED if m in vision_model_names]

    if not ranked:
        ranked = vision_model_names[:1]

    if not ranked:
        pipeline_info["error"] = "Kein Vision-Modell verfügbar"
        return None, pipeline_info

    data = None
    vision_model = None

    for i, model_name in enumerate(ranked):
        model_type = "Cloud" if _is_cloud_model(model_name) else "Lokal"
        pipeline_info["steps"].append(f"Versuch {i + 1}: {model_name} ({model_type})")

        data = extract_invoice(image_bytes, model_name)
        if data:
            vision_model = model_name
            pipeline_info["steps"].append(f"✅ Rechnung erkannt mit {model_name}")
            break
        else:
            pipeline_info["steps"].append(f"❌ {model_name} fehlgeschlagen")

    if not data or not vision_model:
        tried = ", ".join(ranked)
        pipeline_info["error"] = f"Alle Vision-Modelle fehlgeschlagen: {tried}"
        return None, pipeline_info

    pipeline_info["vision_model"] = vision_model
    pipeline_info["vision_data"] = data.copy()
    return data, pipeline_info
