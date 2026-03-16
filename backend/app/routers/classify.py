"""Classifier endpoints — classify, correct, train, info."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.memory import Memory
from app.models.kontenplan import KontoDefault
from app.models.correction import Correction
from app.models.classifier_model import ClassifierModel
from app.services.classifier import TenantClassifier
from typing import Literal

router = APIRouter(prefix="/api/classify", tags=["classify"])

class ClassifyRequest(BaseModel):
    beschreibung: str
    betrag: float = 0
    is_credit: bool = False

class CorrectRequest(BaseModel):
    beschreibung: str
    original_soll: str = ""
    original_haben: str = ""
    corrected_soll: str
    corrected_haben: str
    corrected_mwst_code: str = ""
    corrected_mwst_pct: str = ""

# ── Predict (test endpoint with top-K predictions) ────────────
class PredictRequest(BaseModel):
    beschreibung: str
    betrag: float = 100

@router.post("/predict")
async def predict(
    body: PredictRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clf = TenantClassifier(user.tenant_id, db)
    result = await clf.classify(body.beschreibung, False, body.betrag)

    # Build top predictions from ML model
    top_predictions = []
    model = await clf._load_model()
    if model is not None:
        from app.services.classifier import preprocess
        clean = preprocess(body.beschreibung)
        proba = model.predict_proba([clean])[0]
        sorted_idx = proba.argsort()[::-1][:5]
        defaults = await clf._load_konto_defaults()
        for idx in sorted_idx:
            klass = model.classes_[idx]
            name = defaults.get(klass, {}).get("KontoHaben", "")
            top_predictions.append({
                "klass": klass,
                "name": name,
                "probability": float(proba[idx]),
            })

    # Resolve account names for display
    defaults = await clf._load_konto_defaults()
    kt_soll_name = defaults.get(result.kt_soll, {}).get("KontoHaben", "")
    kt_haben_name = ""

    return {
        "source": result.source,
        "kt_soll": result.kt_soll,
        "kt_soll_name": kt_soll_name,
        "kt_haben": result.kt_haben,
        "kt_haben_name": kt_haben_name,
        "mwst_code": result.mwst_code,
        "mwst_pct": result.mwst_pct,
        "confidence": result.confidence,
        "top_predictions": top_predictions,
    }

# ── Delete (danger zone) ─────────────────────────────────────
@router.delete("/{action}")
async def delete_action(
    action: Literal["memory", "corrections", "model"],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from sqlalchemy import delete

    if action == "memory":
        await db.execute(delete(Memory).where(Memory.tenant_id == user.tenant_id))
    elif action == "corrections":
        await db.execute(delete(Correction).where(Correction.tenant_id == user.tenant_id))
    elif action == "model":
        await db.execute(delete(ClassifierModel).where(ClassifierModel.tenant_id == user.tenant_id))
    else:
        raise HTTPException(400, f"Unbekannte Aktion: {action}")

    await db.commit()
    return {"status": "ok"}

# ── Download (export model/memory/bundle) ─────────────────────
@router.get("/download/{dtype}")
async def download(
    dtype: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import io
    import json
    import zipfile
    from fastapi.responses import Response

    tid = user.tenant_id

    if dtype == "model":
        row = await db.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tid))
        model_row = row.scalar_one_or_none()
        if not model_row or not model_row.model_blob:
            raise HTTPException(404, "Kein Modell vorhanden.")
        return Response(
            content=model_row.model_blob,
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=model.pkl"},
        )

    if dtype == "memory":
        entries = await db.execute(select(Memory).where(Memory.tenant_id == tid))
        data = [
            {"lookup_key": m.lookup_key, "kt_soll": m.kt_soll, "kt_haben": m.kt_haben,
             "mwst_code": m.mwst_code, "mwst_pct": m.mwst_pct}
            for m in entries.scalars().all()
        ]
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=memory.json"},
        )

    if dtype == "bundle":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Model
            row = await db.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tid))
            model_row = row.scalar_one_or_none()
            if model_row and model_row.model_blob:
                zf.writestr("model.pkl", model_row.model_blob)

            # Memory
            entries = await db.execute(select(Memory).where(Memory.tenant_id == tid))
            mem_data = [
                {"lookup_key": m.lookup_key, "kt_soll": m.kt_soll, "kt_haben": m.kt_haben,
                 "mwst_code": m.mwst_code, "mwst_pct": m.mwst_pct}
                for m in entries.scalars().all()
            ]
            zf.writestr("memory.json", json.dumps(mem_data, ensure_ascii=False, indent=2))

            # Corrections
            corr_entries = await db.execute(select(Correction).where(Correction.tenant_id == tid))
            corr_data = [
                {"beschreibung": c.beschreibung, "original_soll": c.original_soll,
                 "corrected_soll": c.corrected_soll, "corrected_haben": c.corrected_haben,
                 "corrected_mwst_code": c.corrected_mwst_code}
                for c in corr_entries.scalars().all()
            ]
            zf.writestr("corrections.json", json.dumps(corr_data, ensure_ascii=False, indent=2))

            # Konto defaults
            kd_entries = await db.execute(select(KontoDefault).where(KontoDefault.tenant_id == tid))
            kd_data = [
                {"konto_soll": k.konto_soll, "konto_haben": k.konto_haben,
                 "mwst_code": k.mwst_code, "mwst_pct": k.mwst_pct}
                for k in kd_entries.scalars().all()
            ]
            zf.writestr("kontenplan.json", json.dumps(kd_data, ensure_ascii=False, indent=2))

        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=buchhaltung_backup.zip"},
        )

    raise HTTPException(400, f"Unbekannter Typ: {dtype}")

# ── Upload (restore model/memory/bundle) ──────────────────────
@router.post("/upload")
async def upload_bundle(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import io
    import json
    import zipfile

    tid = user.tenant_id
    content = await file.read()
    filename = file.filename or ""

    if filename.endswith(".pkl"):
        # Direct model upload
        row = await db.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tid))
        existing = row.scalar_one_or_none()
        if existing:
            existing.model_blob = content
        else:
            db.add(ClassifierModel(tenant_id=tid, model_blob=content))
        await db.commit()
        return {"status": "ok", "restored": ["model"]}

    if filename.endswith(".json"):
        # Memory restore
        data = json.loads(content)
        from sqlalchemy import delete
        await db.execute(delete(Memory).where(Memory.tenant_id == tid))
        for entry in data:
            db.add(Memory(
                tenant_id=tid,
                lookup_key=entry["lookup_key"],
                kt_soll=entry["kt_soll"],
                kt_haben=entry["kt_haben"],
                mwst_code=entry.get("mwst_code", ""),
                mwst_pct=entry.get("mwst_pct", ""),
            ))
        await db.commit()
        return {"status": "ok", "restored": ["memory"]}

    if filename.endswith(".zip"):
        restored = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()

            if "model.pkl" in names:
                model_blob = zf.read("model.pkl")
                row = await db.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tid))
                existing = row.scalar_one_or_none()
                if existing:
                    existing.model_blob = model_blob
                else:
                    db.add(ClassifierModel(tenant_id=tid, model_blob=model_blob))
                restored.append("model")

            if "memory.json" in names:
                from sqlalchemy import delete
                mem_data = json.loads(zf.read("memory.json"))
                await db.execute(delete(Memory).where(Memory.tenant_id == tid))
                for entry in mem_data:
                    db.add(Memory(
                        tenant_id=tid,
                        lookup_key=entry["lookup_key"],
                        kt_soll=entry["kt_soll"],
                        kt_haben=entry["kt_haben"],
                        mwst_code=entry.get("mwst_code", ""),
                        mwst_pct=entry.get("mwst_pct", ""),
                    ))
                restored.append("memory")

            if "corrections.json" in names:
                restored.append("corrections")

            if "kontenplan.json" in names:
                restored.append("kontenplan")

        await db.commit()
        return {"status": "ok", "restored": restored}

    raise HTTPException(400, "Unbekanntes Dateiformat. Erwartet: .zip, .pkl oder .json")

@router.post("/")
async def classify_transaction(
    body: ClassifyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clf = TenantClassifier(user.tenant_id, db)
    result = await clf.classify(body.beschreibung, body.is_credit, body.betrag)
    return {
        "kt_soll": result.kt_soll,
        "kt_haben": result.kt_haben,
        "mwst_code": result.mwst_code,
        "mwst_pct": result.mwst_pct,
        "mwst_amount": result.mwst_amount,
        "confidence": result.confidence,
        "source": result.source,
    }

@router.post("/correct")
async def log_correction(
    body: CorrectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services.classifier import ClassificationResult
    clf = TenantClassifier(user.tenant_id, db)
    original = ClassificationResult(
        kt_soll=body.original_soll, kt_haben=body.original_haben,
        mwst_code="", mwst_pct="", mwst_amount="",
    )
    await clf.log_correction(
        beschreibung=body.beschreibung,
        original=original,
        corrected_soll=body.corrected_soll,
        corrected_haben=body.corrected_haben,
        corrected_mwst_code=body.corrected_mwst_code,
        corrected_mwst_pct=body.corrected_mwst_pct,
    )
    return {"status": "ok"}

@router.post("/train")
async def train_model(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clf = TenantClassifier(user.tenant_id, db)
    result = await clf.train_from_db()
    if not result:
        raise HTTPException(400, "Nicht genug Daten zum Trainieren.")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.get("/info")
async def classifier_info(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return classifier status for the current tenant."""
    mem_result = await db.execute(
        select(func.count()).select_from(Memory).where(Memory.tenant_id == user.tenant_id)
    )
    memory_count = mem_result.scalar() or 0

    corr_result = await db.execute(
        select(func.count()).select_from(Correction).where(Correction.tenant_id == user.tenant_id)
    )
    correction_count = corr_result.scalar() or 0

    model_result = await db.execute(
        select(ClassifierModel).where(ClassifierModel.tenant_id == user.tenant_id)
    )
    model_row = model_result.scalar_one_or_none()

    has_model = model_row is not None and model_row.model_blob is not None
    model_accuracy = 0.0
    total_samples = 0
    classes = 0

    if model_row:
        model_accuracy = model_row.cv_accuracy or 0.0
        total_samples = model_row.total_samples or 0
        classes = model_row.num_classes or 0

    return {
        "has_model": has_model,
        "model_accuracy": model_accuracy,
        "train_accuracy": model_row.train_accuracy if model_row else 0.0,
        "total_samples": total_samples,
        "classes": classes,
        "memory_count": memory_count,
        "correction_count": correction_count,
        "trained_at": str(model_row.updated_at) if model_row and hasattr(model_row, "updated_at") and model_row.updated_at else None,
    }
