from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.classifier_model import ClassifierModel
from app.models.correction import Correction
from app.models.kontenplan import Konto, KontoDefault
from app.models.memory import Memory
from app.models.user import User
from app.services.classifier import ClassificationResult, TenantClassifier, preprocess
from app.services.review_queue import ReviewQueueService
from app.services.usage_meter import UsageMeter

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

class PredictRequest(BaseModel):
    beschreibung: str
    betrag: float = 100

async def _konto_name_map(db: AsyncSession, tenant_id: int) -> dict[str, str]:
    result = await db.execute(select(Konto).where(Konto.tenant_id == tenant_id))
    rows = result.scalars().all()
    return {str(row.konto_nr): row.beschreibung or "" for row in rows}

async def _get_model_row(db: AsyncSession, tenant_id: int) -> ClassifierModel | None:
    result = await db.execute(
        select(ClassifierModel).where(ClassifierModel.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()

async def _get_memory_rows(db: AsyncSession, tenant_id: int) -> list[Memory]:
    result = await db.execute(select(Memory).where(Memory.tenant_id == tenant_id))
    return list(result.scalars().all())

async def _get_correction_rows(db: AsyncSession, tenant_id: int) -> list[Correction]:
    result = await db.execute(select(Correction).where(Correction.tenant_id == tenant_id))
    return list(result.scalars().all())

async def _get_konto_default_rows(db: AsyncSession, tenant_id: int) -> list[KontoDefault]:
    result = await db.execute(select(KontoDefault).where(KontoDefault.tenant_id == tenant_id))
    return list(result.scalars().all())

@router.post("/predict")
@limiter.limit("60/minute")
async def predict(
    request: Request,
    body: PredictRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    clf = TenantClassifier(user.tenant_id, db)
    result = await clf.classify(body.beschreibung, False, body.betrag)

    review_service = ReviewQueueService(user.tenant_id, db)
    review_item = await review_service.enqueue_if_low_confidence(
        body.beschreibung, body.betrag, result
    )
    await UsageMeter(user.tenant_id, db).record("classify")
    await db.commit()

    konto_names = await _konto_name_map(db, user.tenant_id)
    top_predictions: list[dict[str, Any]] = []

    model = await clf._load_model()
    defaults = await clf._load_konto_defaults()

    if model is not None:
        clean = preprocess(body.beschreibung)
        proba = model.predict_proba([clean])[0]
        sorted_idx = proba.argsort()[::-1][:5]

        for idx in sorted_idx:
            klass = str(model.classes_[idx])
            top_predictions.append(
                {
                    "klass": klass,
                    "name": konto_names.get(klass, ""),
                    "default_kt_haben": defaults.get(klass, {}).get("KontoHaben", ""),
                    "probability": float(proba[idx]),
                }
            )

    return {
        "source": result.source,
        "kt_soll": result.kt_soll,
        "kt_soll_name": konto_names.get(result.kt_soll, ""),
        "kt_haben": result.kt_haben,
        "kt_haben_name": konto_names.get(result.kt_haben, ""),
        "mwst_code": result.mwst_code,
        "mwst_pct": result.mwst_pct,
        "confidence": result.confidence,
        "needs_review": review_item is not None,
        "review_id": review_item.id if review_item else None,
        "top_predictions": top_predictions,
    }

@router.delete("/{action}")
async def delete_action(
    action: Literal["memory", "corrections", "model"],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    if action == "memory":
        await db.execute(delete(Memory).where(Memory.tenant_id == user.tenant_id))
    elif action == "corrections":
        await db.execute(delete(Correction).where(Correction.tenant_id == user.tenant_id))
    elif action == "model":
        await db.execute(delete(ClassifierModel).where(ClassifierModel.tenant_id == user.tenant_id))
    else:
        raise HTTPException(status_code=400, detail=f"Unbekannte Aktion: {action}")

    await db.commit()
    return {"status": "ok"}

@router.get("/download/{dtype}")
async def download(
    dtype: Literal["model", "memory", "bundle"],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    tid = user.tenant_id

    if dtype == "model":
        model_row = await _get_model_row(db, tid)
        if not model_row or not model_row.model_blob:
            raise HTTPException(status_code=404, detail="Kein Modell vorhanden.")
        return Response(
            content=model_row.model_blob,
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=model.pkl"},
        )

    if dtype == "memory":
        entries = await _get_memory_rows(db, tid)
        content = json.dumps(
            [
                {
                    "lookup_key": m.lookup_key,
                    "kt_soll": m.kt_soll,
                    "kt_haben": m.kt_haben,
                    "mwst_code": m.mwst_code,
                    "mwst_pct": m.mwst_pct,
                }
                for m in entries
            ],
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=memory.json"},
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        model_row = await _get_model_row(db, tid)
        if model_row and model_row.model_blob:
            zf.writestr("model.pkl", model_row.model_blob)

        mem_entries = await _get_memory_rows(db, tid)
        zf.writestr(
            "memory.json",
            json.dumps(
                [
                    {
                        "lookup_key": m.lookup_key,
                        "kt_soll": m.kt_soll,
                        "kt_haben": m.kt_haben,
                        "mwst_code": m.mwst_code,
                        "mwst_pct": m.mwst_pct,
                    }
                    for m in mem_entries
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

        corr_entries = await _get_correction_rows(db, tid)
        zf.writestr(
            "corrections.json",
            json.dumps(
                [
                    {
                        "beschreibung": c.beschreibung,
                        "original_soll": c.original_soll,
                        "original_haben": c.original_haben,
                        "corrected_soll": c.corrected_soll,
                        "corrected_haben": c.corrected_haben,
                        "corrected_mwst_code": c.corrected_mwst_code,
                        "corrected_mwst_pct": c.corrected_mwst_pct,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in corr_entries
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

        kd_entries = await _get_konto_default_rows(db, tid)
        zf.writestr(
            "kontenplan.json",
            json.dumps(
                [
                    {
                        "konto_soll": k.konto_soll,
                        "konto_haben": k.konto_haben,
                        "mwst_code": k.mwst_code,
                        "mwst_pct": k.mwst_pct,
                    }
                    for k in kd_entries
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

        if model_row:
            zf.writestr(
                "model_info.json",
                json.dumps(
                    {
                        "total_samples": model_row.total_samples,
                        "num_classes": model_row.num_classes,
                        "cv_accuracy": model_row.cv_accuracy,
                        "train_accuracy": model_row.train_accuracy,
                        "sklearn_version": model_row.sklearn_version,
                        "updated_at": model_row.updated_at.isoformat() if model_row.updated_at else None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=buchhaltung_backup.zip"},
    )

@router.post("/upload")
async def upload_bundle(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    tid = user.tenant_id
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pkl"):
        row = await _get_model_row(db, tid)
        if row:
            row.model_blob = content
        else:
            db.add(ClassifierModel(tenant_id=tid, model_blob=content))
        await db.commit()
        return {"status": "ok", "restored": ["model"]}

    if filename.endswith(".json"):
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="Ungültiges Memory-JSON-Format.")

        await db.execute(delete(Memory).where(Memory.tenant_id == tid))
        for entry in data:
            db.add(
                Memory(
                    tenant_id=tid,
                    lookup_key=entry["lookup_key"],
                    kt_soll=entry["kt_soll"],
                    kt_haben=entry["kt_haben"],
                    mwst_code=entry.get("mwst_code", ""),
                    mwst_pct=entry.get("mwst_pct", ""),
                )
            )
        await db.commit()
        return {"status": "ok", "restored": ["memory"]}

    if filename.endswith(".zip"):
        restored: list[str] = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = set(zf.namelist())

            if "model.pkl" in names:
                model_blob = zf.read("model.pkl")
                row = await _get_model_row(db, tid)
                if row:
                    row.model_blob = model_blob
                else:
                    db.add(ClassifierModel(tenant_id=tid, model_blob=model_blob))
                restored.append("model")

            if "memory.json" in names:
                mem_data = json.loads(zf.read("memory.json").decode("utf-8"))
                await db.execute(delete(Memory).where(Memory.tenant_id == tid))
                for entry in mem_data:
                    db.add(
                        Memory(
                            tenant_id=tid,
                            lookup_key=entry["lookup_key"],
                            kt_soll=entry["kt_soll"],
                            kt_haben=entry["kt_haben"],
                            mwst_code=entry.get("mwst_code", ""),
                            mwst_pct=entry.get("mwst_pct", ""),
                        )
                    )
                restored.append("memory")

        await db.commit()
        return {"status": "ok", "restored": restored}

    raise HTTPException(
        status_code=400,
        detail="Unbekanntes Dateiformat. Erwartet: .zip, .pkl oder .json",
    )

@router.post("/")
@limiter.limit("60/minute")
async def classify_transaction(
    request: Request,
    body: ClassifyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    clf = TenantClassifier(user.tenant_id, db)
    result = await clf.classify(body.beschreibung, body.is_credit, body.betrag)

    review_service = ReviewQueueService(user.tenant_id, db)
    review_item = await review_service.enqueue_if_low_confidence(
        body.beschreibung, body.betrag, result
    )
    await UsageMeter(user.tenant_id, db).record("classify")
    await db.commit()

    return {
        "kt_soll": result.kt_soll,
        "kt_haben": result.kt_haben,
        "mwst_code": result.mwst_code,
        "mwst_pct": result.mwst_pct,
        "mwst_amount": result.mwst_amount,
        "confidence": result.confidence,
        "source": result.source,
        "needs_review": review_item is not None,
        "review_id": review_item.id if review_item else None,
    }

@router.post("/correct")
async def log_correction(
    body: CorrectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    clf = TenantClassifier(user.tenant_id, db)
    original = ClassificationResult(
        kt_soll=body.original_soll,
        kt_haben=body.original_haben,
        mwst_code="",
        mwst_pct="",
        mwst_amount="",
    )
    await clf.log_correction(
        beschreibung=body.beschreibung,
        original=original,
        corrected_soll=body.corrected_soll,
        corrected_haben=body.corrected_haben,
        corrected_mwst_code=body.corrected_mwst_code,
        corrected_mwst_pct=body.corrected_mwst_pct,
    )
    await db.commit()
    return {"status": "ok"}

@router.post("/train")
async def train_model(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    clf = TenantClassifier(user.tenant_id, db)
    result = await clf.train_from_db()
    if not result:
        raise HTTPException(status_code=400, detail="Nicht genug Daten zum Trainieren.")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await db.commit()
    return result

@router.get("/info")
async def classifier_info(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    mem_result = await db.execute(
        select(func.count()).select_from(Memory).where(Memory.tenant_id == user.tenant_id)
    )
    memory_count = mem_result.scalar() or 0

    corr_result = await db.execute(
        select(func.count()).select_from(Correction).where(Correction.tenant_id == user.tenant_id)
    )
    correction_count = corr_result.scalar() or 0

    model_row = await _get_model_row(db, user.tenant_id)

    has_model = model_row is not None and model_row.model_blob is not None
    model_accuracy = float(model_row.cv_accuracy or 0.0) if model_row else 0.0
    train_accuracy = float(model_row.train_accuracy or 0.0) if model_row else 0.0
    total_samples = int(model_row.total_samples or 0) if model_row else 0
    classes = int(model_row.num_classes or 0) if model_row else 0

    return {
        "has_model": has_model,
        "model_accuracy": model_accuracy,
        "train_accuracy": train_accuracy,
        "total_samples": total_samples,
        "classes": classes,
        "memory_count": memory_count,
        "correction_count": correction_count,
        "trained_at": model_row.updated_at.isoformat() if model_row and model_row.updated_at else None,
    }
