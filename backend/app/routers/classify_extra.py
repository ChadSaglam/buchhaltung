"""Batch classify, corrections list, memory list endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.correction import Correction
from app.models.memory import Memory
from app.services.classifier import TenantClassifier

router = APIRouter(prefix="/api/classify", tags=["classify"])

class BatchRequest(BaseModel):
    transactions: list[dict]

@router.post("/batch")
async def batch_classify(
    body: BatchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clf = TenantClassifier(user.tenant_id, db)

    results = []
    for i, tx in enumerate(body.transactions):
        beschreibung = tx.get("Beschreibung", "")
        gutschrift = tx.get("Gutschrift")
        betrag = tx.get("Betrag CHF", 0)
        is_credit = gutschrift is not None and gutschrift > 0

        result = await clf.classify(beschreibung, is_credit, float(betrag or 0))
        results.append({
            "nr": i + 1,
            "datum": tx.get("Datum", ""),
            "beschreibung": beschreibung,
            "betrag": betrag,
            "kt_soll": result.kt_soll,
            "kt_haben": result.kt_haben,
            "mwst_code": result.mwst_code,
            "mwst_pct": result.mwst_pct,
            "mwst_amount": result.mwst_amount,
            "source": result.source,
            "confidence": result.confidence,
        })

    return {"results": results, "count": len(results)}

@router.get("/corrections")
async def list_corrections(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(Correction)
        .where(Correction.tenant_id == user.tenant_id)
        .order_by(Correction.id.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    corrections = result.scalars().all()
    return {
        "corrections": [
            {
                "beschreibung": c.beschreibung,
                "original_soll": c.original_soll,
                "original_haben": c.original_haben,
                "corrected_soll": c.corrected_soll,
                "corrected_haben": c.corrected_haben,
                "corrected_mwst_code": c.corrected_mwst_code,
                "created_at": str(c.created_at) if hasattr(c, "created_at") and c.created_at else None,
            }
            for c in corrections
        ],
        "count": len(corrections),
    }

@router.get("/memory")
async def list_memory(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(Memory)
        .where(Memory.tenant_id == user.tenant_id)
        .order_by(Memory.lookup_key)
    )
    result = await db.execute(query)
    entries = result.scalars().all()
    return {
        "entries": [
            {
                "lookup_key": m.lookup_key,
                "kt_soll": m.kt_soll,
                "kt_haben": m.kt_haben,
                "mwst_code": m.mwst_code,
                "mwst_pct": m.mwst_pct,
            }
            for m in entries
        ],
        "count": len(entries),
    }

@router.get("/top-classes")
async def top_classes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.training_data import TrainingRow

    query = (
        select(TrainingRow.kt_soll, func.count().label("anzahl"))
        .where(TrainingRow.tenant_id == user.tenant_id)
        .group_by(TrainingRow.kt_soll)
        .order_by(func.count().desc())
        .limit(20)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        {"konto_soll": r[0], "bezeichnung": "", "anzahl": r[1]}
        for r in rows
    ]
