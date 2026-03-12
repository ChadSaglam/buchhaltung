"""
Ollama vision model integration for Rechnung/receipt scanning.

Supports:
  - Direct Ollama vision models (local + cloud)
  - "Buchhaltung Modell" pipeline: best vision model → structured extraction → ML classifier
"""

from __future__ import annotations

import base64
import json
import re

import requests

OLLAMA_URL = "http://localhost:11434"

# ── Special pipeline name ────────────────────────────────────────────────────

BUCHHALTUNG_MODEL = "🏢 Buchhaltung Modell"
BUCHHALTUNG_DISPLAY = "🏢 Buchhaltung Modell  (Vision + ML-Klassifizierer)"

# ── Invoice extraction schema ────────────────────────────────────────────────

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

PROMPT = """You are an expert Swiss receipt/invoice reader. Analyze this image carefully and extract ALL information.

Extract these fields as JSON:
- vendor: The COMPANY/STORE NAME printed at the TOP of the receipt (e.g. "Migros", "Coop", "Landi Agrola TopShop", "ISO-Center AG"). NOT a date or number.
- date: Transaction DATE in DD.MM.YYYY format (e.g. 07.11.2025). Look near "Datum" or at the top. NOT a time.
- invoice_number: Receipt/invoice number (look for "Bon:", "Rechnung-Nr", "Beleg", "Trx-Id").
- total_amount: TOTAL CHF amount. Look for "Total CHF" or the largest final amount. Use dot as decimal (58.48 not 58,48).
- net_amount: Net amount before VAT ("Netto"). 0 if not visible.
- vat_amount: VAT/MwSt CHF amount. 0 if not visible.
- vat_rate: VAT percentage (Swiss: 8.1 or 2.6). Look for "MWST%" line. 0 if not visible.
- description: What was bought. Read the article/item lines (e.g. "Bleifrei 95", "Lebensmittel").
- line_items: Array of individual items with name and amount if readable.

Respond with ONLY valid JSON. No markdown, no explanation, just the JSON object."""


def _get_model_capabilities(model_name: str) -> list[str]:
    """Query /api/show to get a model's capabilities list."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/show",
            json={"name": model_name},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Ollama returns {"capabilities": ["completion", "vision", ...]}
            caps = data.get("capabilities") or []
            return [c.lower() for c in caps]
    except Exception:
        pass
    return []


def _parse_model_size(model_info: dict) -> float:
    """Extract model size in GB from the /api/tags entry for sorting."""
    size_bytes = model_info.get("size", 0)
    if size_bytes and isinstance(size_bytes, (int, float)):
        return size_bytes / (1024 ** 3)
    return 0.0


def check_ollama_status() -> tuple[bool, str, list[str], list[str]]:
    """Check if Ollama is running and detect model capabilities dynamically.

    Returns:
        (ok, best_vision_model_or_error, all_display_models, vision_model_names)

    all_display_models: list of display strings for the dropdown.
        The first entry is always "🏢 Buchhaltung Modell" if an ML model exists.
        Vision models get a ' 👁 Vision' suffix.
        Cloud models get a ' ☁ Cloud' suffix.
    vision_model_names: the raw model names that have vision capability.
    """
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, "Ollama antwortet nicht. Bitte starten Sie Ollama.", [], []

        models = resp.json().get("models", [])
        if not models:
            return False, "Keine Modelle installiert. Bitte `ollama pull gemma3:4b` ausführen.", [], []

        # Query each model's capabilities via /api/show
        vision_names: list[str] = []
        model_caps: dict[str, list[str]] = {}
        is_cloud = lambda n: n.endswith(":cloud") or n.endswith("-cloud")
        for m in models:
            name = m["name"]
            caps = _get_model_capabilities(name)
            model_caps[name] = caps
            if "vision" in caps:
                vision_names.append(name)

        # Build display list: vision models first (sorted), then others
        model_size = {m["name"]: _parse_model_size(m) for m in models}

        def display_name(name: str) -> str:
            tags = []
            if name in vision_names:
                tags.append("👁 Vision")
            if is_cloud(name):
                tags.append("⚡ Cloud/Schnell")
            else:
                size_gb = model_size.get(name, 0)
                if size_gb > 0.1:
                    tags.append(f"{size_gb:.1f} GB")
                    if size_gb > 10:
                        tags.append("🐢 Langsam")
            suffix = f"  ({', '.join(tags)})" if tags else ""
            return f"{name}{suffix}"

        # Sort vision models: cloud first (fast), then local by size ascending (smaller=faster)
        vision_cloud = [n for n in vision_names if is_cloud(n)]
        vision_local = [n for n in vision_names if not is_cloud(n)]
        vision_cloud_sorted = sorted(vision_cloud, key=lambda n: n)
        vision_local_sorted = sorted(vision_local, key=lambda n: model_size.get(n, 0))

        non_vision = [m["name"] for m in models if m["name"] not in vision_names]
        non_vision_sorted = sorted(non_vision, key=lambda n: model_size.get(n, 0), reverse=True)

        ordered_names = vision_cloud_sorted + vision_local_sorted + non_vision_sorted
        display_list = [display_name(n) for n in ordered_names]

        # Check if Buchhaltung ML model exists — if so, prepend as first option
        has_buchhaltung_model = _check_buchhaltung_model()
        if has_buchhaltung_model and vision_names:
            display_list = [BUCHHALTUNG_DISPLAY] + display_list

        # Pick best default: prefer smallest local vision model (fastest), or cloud vision
        if vision_local_sorted:
            best = vision_local_sorted[0]  # smallest local = fastest
        elif vision_cloud_sorted:
            best = vision_cloud_sorted[0]
        else:
            best = ordered_names[0]

        return True, best, display_list, vision_names

    except requests.ConnectionError:
        return False, "Ollama ist nicht erreichbar. Bitte starten Sie Ollama (`ollama serve`).", [], []
    except Exception as e:
        return False, f"Fehler bei der Ollama-Verbindung: {e}", [], []


def _check_buchhaltung_model() -> bool:
    """Check if the Buchhaltung ML classifier model exists."""
    from pathlib import Path
    model_path = Path(__file__).resolve().parent.parent / "data" / "classifier_model.pkl"
    return model_path.exists()


def get_vision_models_ranked(vision_model_names: list[str]) -> list[str]:
    """Rank vision models for the Buchhaltung pipeline.

    Returns ALL vision models in priority order for fallback.
    Priority: smallest local (most reliable) → larger local → cloud (often can't see images).
    Cloud models are deprioritized because many report 'vision' capability but
    actually cannot process images (return null/empty).
    """
    if not vision_model_names:
        return []

    is_cloud = lambda n: n.endswith(":cloud") or n.endswith("-cloud")
    cloud = [n for n in vision_model_names if is_cloud(n)]
    local = [n for n in vision_model_names if not is_cloud(n)]

    # Sort local by size (smallest = fastest + most reliable for vision)
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            size_map = {m["name"]: _parse_model_size(m) for m in models}
            local = sorted(local, key=lambda n: size_map.get(n, 999))
    except Exception:
        pass

    # Local first (reliable), cloud last (often broken for images)
    return local + sorted(cloud)


def get_best_vision_model(vision_model_names: list[str]) -> str | None:
    """Pick the best vision model. Returns first from ranked list."""
    ranked = get_vision_models_ranked(vision_model_names)
    return ranked[0] if ranked else None


def is_buchhaltung_model(display_name: str) -> bool:
    """Check if the selected display name is the Buchhaltung pipeline."""
    return display_name.startswith("🏢")


def validate_and_fix_extraction(data: dict) -> dict:
    """Post-process AI extraction to fix common errors."""
    if not data:
        return data

    vendor = str(data.get("vendor", ""))
    if re.match(r"^\d{2}[.:/-]\d{2}[.:/-]\d{2,4}$", vendor) or re.match(r"^\d{2}:\d{2}", vendor):
        data["vendor"] = ""

    date_val = str(data.get("date", ""))
    if re.match(r"^\d{2}:\d{2}", date_val):
        data["date"] = ""
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", date_val)
    if m:
        y = int(m.group(3))
        full_y = 2000 + y if y < 50 else 1900 + y
        data["date"] = f"{m.group(1)}.{m.group(2)}.{full_y}"

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
        if abs(vat - closest) < 1.0:
            data["vat_rate"] = closest
        else:
            data["vat_rate"] = 0

    desc = str(data.get("description", ""))
    if desc.lower() in ["", "unbekannt", "unknown", "n/a", "none"]:
        data["description"] = ""

    return data


def extract_invoice(image_bytes: bytes, model: str) -> dict | None:
    """Send an invoice image to Ollama and extract structured data.

    Returns the extracted dict, or None on failure.
    Stores debug info in st.session_state['_last_vision_debug'] for troubleshooting.
    """
    import streamlit as st

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    debug = {"model": model, "image_size_kb": len(image_bytes) / 1024}

    # Try with structured format first, fall back to plain text
    for attempt, use_format in enumerate(["schema", "plain"]):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT, "images": [img_b64]}],
            "stream": False,
            "options": {"temperature": 0},
        }

        # Only use format schema on first attempt — some models don't support it
        if use_format == "schema":
            payload["format"] = INVOICE_SCHEMA

        try:
            resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
            debug[f"attempt_{attempt}_status"] = resp.status_code

            if resp.status_code != 200:
                debug[f"attempt_{attempt}_error"] = resp.text[:500]
                continue

            resp_json = resp.json()
            content = resp_json.get("message", {}).get("content", "")
            debug[f"attempt_{attempt}_response_len"] = len(content)
            debug[f"attempt_{attempt}_raw"] = content[:1000]

            if not content or not content.strip():
                debug[f"attempt_{attempt}_error"] = "Empty response from model"
                continue

            # Try to parse JSON
            data = None
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from surrounding text
                brace_start = content.find("{")
                brace_end = content.rfind("}")
                if brace_start != -1 and brace_end > brace_start:
                    json_str = content[brace_start:brace_end + 1]
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        debug[f"attempt_{attempt}_parse_error"] = f"Could not parse: {json_str[:200]}"

            if data and isinstance(data, dict):
                # Check we got at least vendor or total
                has_vendor = bool(data.get("vendor", ""))
                has_total = data.get("total_amount", 0) not in (0, None, "")
                if has_vendor or has_total:
                    data = validate_and_fix_extraction(data)
                    debug["success"] = True
                    debug["final_data"] = data
                    st.session_state["_last_vision_debug"] = debug
                    return data
                else:
                    debug[f"attempt_{attempt}_error"] = f"Parsed but empty data: {data}"
            else:
                debug[f"attempt_{attempt}_error"] = "No valid JSON found"

        except requests.Timeout:
            debug[f"attempt_{attempt}_error"] = "Request timed out (180s)"
        except Exception as e:
            debug[f"attempt_{attempt}_error"] = str(e)

    debug["success"] = False
    st.session_state["_last_vision_debug"] = debug
    return None


def extract_invoice_with_buchhaltung(image_bytes: bytes, vision_model_names: list[str]) -> tuple[dict | None, dict]:
    """Full Buchhaltung pipeline: Vision extraction → ML classification → enriched result.

    Tries multiple vision models with automatic fallback if one fails.

    Returns:
        (extracted_data, pipeline_info) where pipeline_info contains details about
        which models were used, classification result, etc.
    """
    import streamlit as st

    pipeline_info = {
        "pipeline": "buchhaltung",
        "steps": [],
    }

    # Step 1: Get ranked list of vision models to try
    ranked_models = get_vision_models_ranked(vision_model_names)
    if not ranked_models:
        pipeline_info["error"] = "Kein Vision-Modell verfügbar"
        return None, pipeline_info

    # Step 2: Try vision models in order until one succeeds
    data = None
    vision_model = None
    max_attempts = min(3, len(ranked_models))  # Try up to 3 models

    for i, model_name in enumerate(ranked_models[:max_attempts]):
        is_cloud = model_name.endswith(":cloud") or model_name.endswith("-cloud")
        model_type = "☁ Cloud" if is_cloud else "💻 Lokal"
        pipeline_info["steps"].append(f"👁 Versuch {i+1}: {model_name} ({model_type})")

        data = extract_invoice(image_bytes, model_name)
        if data:
            vision_model = model_name
            pipeline_info["steps"].append(f"✅ Rechnung erkannt mit {model_name}")
            break
        else:
            pipeline_info["steps"].append(f"❌ {model_name} fehlgeschlagen")

    if not data or not vision_model:
        tried = ", ".join(ranked_models[:max_attempts])
        pipeline_info["error"] = f"Alle Vision-Modelle fehlgeschlagen ({tried})"
        return None, pipeline_info

    pipeline_info["vision_model"] = vision_model
    pipeline_info["vision_data"] = data.copy()

    # Step 3: Classify with ML model
    try:
        clf = st.session_state.get("classifier")
        if clf and clf.has_model:
            vendor = data.get("vendor", "")
            description = data.get("description", "")
            total = float(data.get("total_amount", 0))

            # Build search text from vendor + description + line items
            search_parts = [vendor, description]
            line_items = data.get("line_items", [])
            if line_items and isinstance(line_items, list):
                for item in line_items[:5]:
                    if isinstance(item, dict):
                        search_parts.append(str(item.get("item", "")))

            combined = " ".join(p for p in search_parts if p).strip()

            if combined:
                is_credit = any(kw in combined.lower() for kw in ["gutschrift", "zahlung erhalten", "einzahlung"])
                result = clf.classify(combined, is_credit, total)

                data["_classification"] = {
                    "kt_soll": result.kt_soll,
                    "kt_haben": result.kt_haben,
                    "mwst_code": result.mwst_code,
                    "mwst_pct": result.mwst_pct,
                    "mwst_amount": result.mwst_amount,
                    "confidence": result.confidence,
                    "source": result.source,
                    "search_text": combined,
                }

                source_icon = {"Gedächtnis": "🧠", "ML": "🤖", "Regeln": "📋"}.get(result.source, "❓")
                pipeline_info["steps"].append(
                    f"{source_icon} Klassifiziert: {result.kt_soll} ({result.source}, {result.confidence:.0%})"
                )
                pipeline_info["classification"] = data["_classification"]
            else:
                pipeline_info["steps"].append("⚠️ Kein Text für Klassifizierung")
        else:
            pipeline_info["steps"].append("⚠️ ML-Modell nicht geladen")

    except Exception as e:
        pipeline_info["steps"].append(f"⚠️ Klassifizierung: {e}")

    return data, pipeline_info
