from __future__ import annotations
import json
import asyncio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.ollama_vision import (
    check_ollama_status, extract_invoice, _is_cloud_model, _status_cache
)
from app.services.classifier import TenantClassifier, calc_mwst

router = APIRouter(prefix="/api/scanner", tags=["scanner"])
MAX_FILE_SIZE = 20 * 1024 * 1024


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/status")
async def scanner_status():
    return check_ollama_status()


@router.post("/extract")
async def extract_invoice_endpoint(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.content_type or not (
        file.content_type.startswith("image") or file.content_type == "application/pdf"
    ):
        raise HTTPException(400, "Nur Bilder (JPG, PNG, WebP) oder PDF erlaubt.")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, f"Datei zu gross (max {MAX_FILE_SIZE // 1024 // 1024} MB).")

    status = check_ollama_status()
    if not status["ok"]:
        raise HTTPException(503, status.get("error", "Ollama nicht erreichbar."))

    vision_models: list[str] = list(status.get("vision_models", []))

    if not vision_models:
        raise HTTPException(503, "Kein Vision-Modell verfügbar.")

    # Build ranked list — user selection takes priority
    if model and model.strip():
        selected = model.strip()
        # User's choice first, then fallbacks
        ranked = [selected] + [m for m in vision_models if m != selected][:2]
    else:
        # Auto mode: prefer local gemma3:12b, then cloud
        PREFERRED = ["gemma3:12b", "gemma3:4b", "kimi-k2.5:cloud"]
        ranked = [m for m in PREFERRED if m in vision_models]
        if not ranked:
            ranked = vision_models[:2]

    async def generate():
        yield _sse_event("step", {"icon": "📤", "label": "Bild wird hochgeladen", "status": "done"})
        await asyncio.sleep(0.1)

        yield _sse_event("step", {"icon": "🔍", "label": f"{len(ranked)} Modell(e) werden getestet", "status": "active"})

        data = None
        vision_model = None

        for i, model_name in enumerate(ranked):
            model_type = "Cloud" if _is_cloud_model(model_name) else "Lokal"
            yield _sse_event("step", {
                "icon": "🤖",
                "label": f"Versuch {i+1}: {model_name} ({model_type})",
                "status": "active",
                "model": model_name,
            })

            result = await asyncio.to_thread(extract_invoice, image_bytes, model_name)

            if result:
                data = result
                vision_model = model_name
                yield _sse_event("step", {
                    "icon": "✅",
                    "label": f"Rechnung erkannt mit {model_name}",
                    "status": "done",
                    "model": model_name,
                })
                break
            else:
                yield _sse_event("step", {
                    "icon": "❌",
                    "label": f"{model_name} fehlgeschlagen",
                    "status": "failed",
                    "model": model_name,
                })

        if not data:
            yield _sse_event("error", {"message": "Alle Vision-Modelle fehlgeschlagen"})
            return

        # Classification
        yield _sse_event("step", {"icon": "🧠", "label": "ML-Klassifizierung läuft", "status": "active"})

        vendor = data.get("vendor", "")
        description = data.get("description", "")
        total_amount = float(data.get("total_amount", 0) or 0)
        vat_rate = float(data.get("vat_rate", 0) or 0)

        is_credit = any(
            kw in f"{vendor} {description}".lower()
            for kw in ["gutschrift", "zahlung erhalten", "einzahlung"]
        )

        clf = TenantClassifier(user.tenant_id, db)
        candidates = [
            vendor.strip(),
            f"{vendor} {description.split('(')[0].split(',')[0]}".strip(),
            f"{vendor} {description}".strip(),
        ]
        candidates = [c for c in candidates if c]

        best_result = None
        for text in candidates:
            cl_result = await clf.classify(text, is_credit, total_amount)
            if best_result is None or cl_result.confidence > best_result.confidence:
                best_result = cl_result
            if cl_result.confidence >= 0.7:
                break

        cl = best_result

        if vat_rate > 0:
            if vat_rate >= 7.0:
                cl.mwst_pct = "8.10"
                cl.mwst_code = cl.mwst_code or "I81"
            elif vat_rate >= 2.0:
                cl.mwst_pct = "2.60"
                cl.mwst_code = cl.mwst_code or "I25"
            cl.mwst_amount = calc_mwst(total_amount, cl.mwst_pct)

        data["kt_soll"] = cl.kt_soll
        data["kt_haben"] = cl.kt_haben
        data["mwst_code"] = cl.mwst_code
        data["mwst_pct"] = cl.mwst_pct
        data["mwst_amount"] = cl.mwst_amount
        data["classification_confidence"] = cl.confidence
        data["classification_source"] = cl.source

        yield _sse_event("step", {
            "icon": "🎯",
            "label": f"Kontierung: {cl.kt_soll}/{cl.kt_haben} ({cl.source}, {cl.confidence:.0%})",
            "status": "done",
        })

        yield _sse_event("result", {"data": data, "vision_model": vision_model})

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.get("/vision-status")
async def vision_status(refresh: bool = False):
    """Full vision status for frontend."""
    if refresh:
        _status_cache["data"] = None
        _status_cache["ts"] = 0

    status = check_ollama_status()
    vision_models = list(status.get("vision_models", []))
    all_models = status.get("models", [])
    best = vision_models[0] if vision_models else None
    return {
        "ok": status["ok"] and bool(best),
        "error": status.get("error"),
        "models": [{"name": m} for m in all_models],
        "vision_models": vision_models,
        "best_vision": best,
    }
