"""Kontenplan CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.kontenplan import Konto, KontoDefault

router = APIRouter(prefix="/api/kontenplan", tags=["kontenplan"])


class KontenplanUpdate(BaseModel):
    kontenplan: dict[str, str]


@router.get("/")
async def get_kontenplan(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Konto).where(Konto.tenant_id == user.tenant_id)
    )
    rows = result.scalars().all()
    plan = {row.konto_nr: row.beschreibung for row in rows}
    return {"kontenplan": plan}


@router.put("/")
async def update_kontenplan(
    body: KontenplanUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(Konto).where(Konto.tenant_id == user.tenant_id)
    )
    for row in existing.scalars().all():
        await db.delete(row)

    for konto_nr, beschreibung in body.kontenplan.items():
        db.add(Konto(
            tenant_id=user.tenant_id,
            konto_nr=konto_nr,
            beschreibung=beschreibung,
        ))

    await db.commit()
    return {"status": "ok", "count": len(body.kontenplan)}


@router.get("/defaults")
async def get_defaults(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(KontoDefault).where(KontoDefault.tenant_id == user.tenant_id)
    )
    defaults = {
        row.konto_soll: {
            "KontoHaben": row.konto_haben,
            "MwStCode": row.mwst_code,
            "MwStUStProz": row.mwst_pct,
        }
        for row in result.scalars().all()
    }
    return {"defaults": defaults}
