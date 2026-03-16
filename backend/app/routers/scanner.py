from __future__ import annotations
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.ollama_vision import check_ollama_status, extract_invoice_with_pipeline
from app.services.classifier import TenantClassifier, calc_mwst

router = APIRouter(prefix="/api/scanner", tags=["scanner"])
MAX_FILE_SIZE = 20 * 1024 * 1024


@router.get("/status")
async def scanner_status():
    return check_ollama_status()


@router.post("/extract")
async def extract_invoice(
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

    if model and model.strip():
        model = model.strip()
        if model in vision_models:
            vision_models = [model] + [m for m in vision_models if m != model]
        else:
            vision_models = [model] + vision_models

    if not vision_models:
        raise HTTPException(503, "Kein Vision-Modell verfügbar. Installiere z.B. `ollama pull gemma3:4b`")

    data, pipeline_info = extract_invoice_with_pipeline(image_bytes, vision_models)

    if not data:
        error_msg = pipeline_info.get("error", "Konnte Rechnung nicht lesen.")
        raise HTTPException(422, error_msg)

    # ── ML Classification ────────────────────────────────────────────
    vendor = data.get("vendor", "")
    description = data.get("description", "")
    total_amount = float(data.get("total_amount", 0) or 0)
    vat_rate = float(data.get("vat_rate", 0) or 0)

    is_credit = any(kw in f"{vendor} {description}".lower() for kw in ["gutschrift", "zahlung erhalten", "einzahlung"])

    clf = TenantClassifier(user.tenant_id, db)

    # Try multiple text variations — best match wins
    candidates = [
        vendor.strip(),                                              # "Landi"
        f"{vendor} {description.split('(')[0].split(',')[0]}".strip(),  # "Landi BLEIFREI 95"
        f"{vendor} {description}".strip(),                           # full text
    ]
    candidates = [c for c in candidates if c]  # remove empties

    best_result = None
    for text in candidates:
        result = await clf.classify(text, is_credit, total_amount)
        if best_result is None or result.confidence > best_result.confidence:
            best_result = result
        if result.confidence >= 0.7:
            break  # good enough

    result = best_result

    # Override MwSt if vision detected a rate
    if vat_rate > 0:
        if vat_rate >= 7.0:
            result.mwst_pct = "8.10"
            result.mwst_code = result.mwst_code or "I81"
        elif vat_rate >= 2.0:
            result.mwst_pct = "2.60"
            result.mwst_code = result.mwst_code or "I25"
        result.mwst_amount = calc_mwst(total_amount, result.mwst_pct)

    # Merge classification into response
    data["kt_soll"] = result.kt_soll
    data["kt_haben"] = result.kt_haben
    data["mwst_code"] = result.mwst_code
    data["mwst_pct"] = result.mwst_pct
    data["mwst_amount"] = result.mwst_amount
    data["classification_confidence"] = result.confidence
    data["classification_source"] = result.source

    pipeline_info["steps"] = pipeline_info.get("steps", []) + [
        f"🎯 Kontierung: {result.kt_soll}/{result.kt_haben} ({result.source}, {result.confidence:.0%})"
    ]

    return {"data": data, "pipeline_info": pipeline_info}

@router.get("/vision-status")
async def vision_status():
    """Endpoint for frontend Modell Manager vision card."""
    status = check_ollama_status()
    vision_models = list(status.get("vision_models", []))
    best = vision_models[0] if vision_models else None
    return {
        "available": status["ok"] and bool(best),
        "model_name": best,
        "model_count": len(vision_models),
        "is_cloud": best.endswith(":cloud") if best else False,
    }