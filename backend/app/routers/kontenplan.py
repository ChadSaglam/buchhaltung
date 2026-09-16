"""Kontenplan CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.core.uploads import MAX_IMPORT_BYTES, MAX_KONTENPLAN_ENTRIES, check_count, read_upload
from app.models.kontenplan import Konto, KontoDefault
from app.models.user import User
from app.schemas.kontenplan import (
    KontenplanImportErgebnis,
    KontenplanImportVorschau,
    KontenplanImportZeile,
    KontenplanResponse,
    KontenplanSaved,
    KontoDefaultsResponse,
)
from app.services import kontenplan_import
from app.services.audit_log import audit

router = APIRouter(prefix="/api/kontenplan", tags=["kontenplan"])


class KontenplanUpdate(BaseModel):
    kontenplan: dict[str, str]


@router.get("/", response_model=KontenplanResponse)
async def get_kontenplan(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Konto).where(Konto.tenant_id == user.tenant_id))
    rows = result.scalars().all()
    plan = {row.konto_nr: row.beschreibung or "" for row in rows}
    return {"kontenplan": plan}


@router.put("/", response_model=KontenplanSaved)
async def update_kontenplan(
    body: KontenplanUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    # A small JSON body, one row each (B-54).
    check_count(body.kontenplan, max_items=MAX_KONTENPLAN_ENTRIES, label="Konten")

    existing = await db.execute(select(Konto).where(Konto.tenant_id == user.tenant_id))
    for row in existing.scalars().all():
        await db.delete(row)

    for konto_nr, beschreibung in body.kontenplan.items():
        db.add(
            Konto(
                tenant_id=user.tenant_id,
                konto_nr=konto_nr,
                beschreibung=beschreibung,
            )
        )

    await audit(db, user, "kontenplan.update", target_type="kontenplan", konten=len(body.kontenplan))
    await db.commit()
    return {"status": "ok", "count": len(body.kontenplan)}


async def _bestand(db: AsyncSession, tenant_id: int) -> dict[str, str]:
    rows = (await db.execute(select(Konto).where(Konto.tenant_id == tenant_id))).scalars().all()
    return {row.konto_nr: row.beschreibung or "" for row in rows}


def _als_vorschau(v: kontenplan_import.Vorschau) -> KontenplanImportVorschau:
    return KontenplanImportVorschau(
        zeilen=[
            KontenplanImportZeile(
                konto=z.konto,
                bezeichnung=z.bezeichnung,
                status=z.status,
                bisher=z.bisher,
                grund=z.grund,
                quelle=z.quelle,
            )
            for z in v.zeilen
        ],
        entfaellt=v.entfaellt,
        spalte_konto=v.spalte_konto,
        spalte_bezeichnung=v.spalte_bezeichnung,
        zaehler=v.zaehler(),
    )


async def _lesen(file: UploadFile, db: AsyncSession, tenant_id: int) -> kontenplan_import.Vorschau:
    inhalt = await read_upload(file, max_bytes=MAX_IMPORT_BYTES, label="Kontenplan")
    try:
        return kontenplan_import.lesen(file.filename or "", inhalt, await _bestand(db, tenant_id))
    except kontenplan_import.KontenplanDateiFehler as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import/vorschau", response_model=KontenplanImportVorschau)
async def import_vorschau(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Was der Import tun würde (B-20). Schreibt nichts.

    Eigener Schritt, weil ``PUT /api/kontenplan/`` den ganzen Plan ersetzt: wer
    eine Teilliste hochlädt, soll *vorher* sehen, welche Konten dabei
    verschwinden würden.
    """
    return _als_vorschau(await _lesen(file, db, user.tenant_id))


@router.post("/import", response_model=KontenplanImportErgebnis)
async def import_anwenden(
    file: UploadFile = File(...),
    modus: str = Form(default=kontenplan_import.ERGAENZEN),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Den Import ausführen (B-20).

    Die Datei wird ein zweites Mal gelesen statt die Vorschau zwischenzuspeichern:
    eine Serverkopie zwischen zwei Klicks wäre Zustand, der veralten kann, und
    das Ergebnis meldet ohnehin, was tatsächlich passiert ist.
    """
    if modus not in kontenplan_import.MODI:
        raise HTTPException(400, f"Unbekannter Modus: {modus}")

    bestand = await _bestand(db, user.tenant_id)
    vorschau = await _lesen(file, db, user.tenant_id)
    neu_plan = kontenplan_import.anwenden(bestand, vorschau, modus)
    check_count(neu_plan, max_items=MAX_KONTENPLAN_ENTRIES, label="Konten")

    for row in (await db.execute(select(Konto).where(Konto.tenant_id == user.tenant_id))).scalars().all():
        await db.delete(row)
    for konto_nr, beschreibung in neu_plan.items():
        db.add(Konto(tenant_id=user.tenant_id, konto_nr=konto_nr, beschreibung=beschreibung))

    zaehler = vorschau.zaehler()
    entfernt = len(set(bestand) - set(neu_plan))
    await audit(
        db,
        user,
        "kontenplan.update",
        target_type="kontenplan",
        konten=len(neu_plan),
        modus=modus,
        quelle="import",
    )
    await db.commit()
    return KontenplanImportErgebnis(
        status="ok",
        modus=modus,
        count=len(neu_plan),
        neu=zaehler[kontenplan_import.NEU],
        geaendert=zaehler[kontenplan_import.GEAENDERT],
        entfernt=entfernt,
    )


@router.get("/defaults", response_model=KontoDefaultsResponse)
async def get_defaults(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(KontoDefault).where(KontoDefault.tenant_id == user.tenant_id))
    defaults = {
        row.konto_soll: {
            "KontoHaben": row.konto_haben or "",
            "MwStCode": row.mwst_code or "",
            "MwStUStProz": row.mwst_pct or "",
        }
        for row in result.scalars().all()
    }
    return {"defaults": defaults}
