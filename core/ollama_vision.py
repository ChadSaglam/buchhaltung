"""
Ollama vision model integration for Rechnung/receipt scanning.
"""

from __future__ import annotations

import base64
import json
import re

import requests

OLLAMA_URL = "http://localhost:11434"

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
    },
    "required": ["vendor", "date", "total_amount", "description"],
}

PROMPT = """Look at this Swiss receipt/invoice image. Extract EXACTLY these fields:

1. vendor: The COMPANY NAME at the TOP of the receipt (the store/business name, e.g. "Migros", "Coop", "Landi Agrola", "ISO-Center AG"). This is NOT a date or number.
2. date: The DATE of the transaction in DD.MM.YYYY format (e.g. 07.11.2025). Look near "Datum" or the main date on the receipt. Do NOT use the time (HH:MM:SS).
3. invoice_number: The receipt/invoice number (look for "Bon:", "Rechnung-Nr", "Beleg").
4. total_amount: The TOTAL amount in CHF. Look for "Total CHF" or the final amount. Use dot as decimal (e.g. 58.48 not 58,48). Do NOT use transaction IDs or Kasse numbers.
5. net_amount: Net amount before VAT ("Netto"). Use 0 if not shown.
6. vat_amount: The VAT/MwSt amount in CHF ("MWST" amount). Use 0 if not shown.
7. vat_rate: The VAT percentage ("MWST%"). Swiss rates are 8.1 or 2.6. Use 0 if not shown.
8. description: What was bought/paid for. Read the article/item names (e.g. "Bleifrei 95", "Lebensmittel", "Isoliermaterial").

EXAMPLE: For an Agrola gas station receipt showing "Bleifrei 95, Total CHF 58.48, MWST% 8.10":
{"vendor": "Landi Agrola TopShop", "date": "07.11.2025", "invoice_number": "69730", "total_amount": 58.48, "net_amount": 54.10, "vat_amount": 4.38, "vat_rate": 8.1, "description": "Bleifrei 95 Benzin"}

Now extract the data from this image:"""


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
        (ok, best_model_or_error, all_display_models, vision_model_names)

    all_display_models: list of display strings for the dropdown.
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
        for m in models:
            name = m["name"]
            caps = _get_model_capabilities(name)
            model_caps[name] = caps
            if "vision" in caps:
                vision_names.append(name)

        # Build display list: vision models first (sorted by size desc), then others
        model_size = {m["name"]: _parse_model_size(m) for m in models}
        is_cloud = lambda n: n.endswith(":cloud") or n.endswith("-cloud")

        def display_name(name: str) -> str:
            tags = []
            if name in vision_names:
                tags.append("👁 Vision")
            if is_cloud(name):
                tags.append("☁ Cloud")
            suffix = f"  ({', '.join(tags)})" if tags else ""
            return f"{name}{suffix}"

        # Sort: vision first, within each group by size descending
        vision_sorted = sorted(vision_names, key=lambda n: model_size.get(n, 0), reverse=True)
        non_vision = [m["name"] for m in models if m["name"] not in vision_names]
        non_vision_sorted = sorted(non_vision, key=lambda n: model_size.get(n, 0), reverse=True)

        ordered_names = vision_sorted + non_vision_sorted
        display_list = [display_name(n) for n in ordered_names]

        # Pick best default: largest vision model, or largest overall
        best = vision_sorted[0] if vision_sorted else ordered_names[0]

        return True, best, display_list, vision_names

    except requests.ConnectionError:
        return False, "Ollama ist nicht erreichbar. Bitte starten Sie Ollama (`ollama serve`).", [], []
    except Exception as e:
        return False, f"Fehler bei der Ollama-Verbindung: {e}", [], []


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
    """Send an invoice image to Ollama and extract structured data."""
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT, "images": [img_b64]}],
        "stream": False,
        "format": INVOICE_SCHEMA,
        "options": {"temperature": 0},
    }

    try:
        resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
        if resp.status_code != 200:
            return None

        content = resp.json().get("message", {}).get("content", "")

        data = None
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if data:
            data = validate_and_fix_extraction(data)

        return data

    except requests.Timeout:
        return None
    except Exception:
        return None
