"""Export & email endpoints — Banana TXT, Excel, CSV, Email."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.booking import Booking
from app.services.export import df_to_banana_tsv, df_to_styled_excel, df_to_csv
from app.services.email_sender import is_email_configured, send_bookkeeping_email

router = APIRouter(prefix="/api/export", tags=["export"])

class BuchungRowExport(BaseModel):
    nr: int
    datum: str
    beleg: str
    rechnung: str
    beschreibung: str
    kt_soll: str
    kt_haben: str
    betrag: float
    mwstcode: str
    artbetrag: str
    mwstpct: str
    mwstchf: float | str
    ks3: str

class ExportRequest(BaseModel):
    rows: list[BuchungRowExport]

def _rows_to_df(rows: list[BuchungRowExport]) -> pd.DataFrame:
    data = []
    for r in rows:
        data.append({
            "Nr": r.nr,
            "Datum": r.datum,
            "Beleg": r.beleg,
            "Rechnung": r.rechnung,
            "Beschreibung": r.beschreibung,
            "KtSoll": r.kt_soll,
            "KtHaben": r.kt_haben,
            "Betrag CHF": r.betrag,
            "MwStUSt-Code": r.mwstcode,
            "Art Betrag": r.artbetrag,
            "MwSt-%": r.mwstpct,
            "Gebuchte MwStUSt CHF": float(r.mwstchf) if r.mwstchf else 0,
            "KS3": r.ks3,
        })
    return pd.DataFrame(data)

async def _get_bookings_df(
    db: AsyncSession, tenant_id: int, source: str | None = None
) -> pd.DataFrame:
    query = select(Booking).where(Booking.tenant_id == tenant_id)
    if source:
        query = query.where(Booking.source == source)
    query = query.order_by(Booking.id)
    result = await db.execute(query)
    bookings = result.scalars().all()

    rows = []
    for b in bookings:
        rows.append({
            "Nr": b.id,
            "Datum": b.datum,
            "Beleg": b.beleg or "",
            "Rechnung": b.rechnung or "",
            "Beschreibung": b.beschreibung or "",
            "KtSoll": b.kt_soll or "",
            "KtHaben": b.kt_haben or "",
            "Betrag CHF": b.betrag or 0,
            "MwStUSt-Code": b.mwst_code or "",
            "Art Betrag": "",
            "MwSt-%": b.mwst_pct or "",
            "Gebuchte MwStUSt CHF": b.mwst_amount or 0,
            "KS3": "",
        })
    return pd.DataFrame(rows)


# ── POST routes (accept frontend state data) ──
@router.post("/banana")
async def export_banana_post(body: ExportRequest):
    if not body.rows:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    df = _rows_to_df(body.rows)
    content = df_to_banana_tsv(df)
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=banana_import.txt"},
    )

@router.post("/excel")
async def export_excel_post(body: ExportRequest):
    if not body.rows:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    df = _rows_to_df(body.rows)
    content = df_to_styled_excel(df)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=buchhaltung.xlsx"},
    )

@router.post("/csv")
async def export_csv_post(body: ExportRequest):
    if not body.rows:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    df = _rows_to_df(body.rows)
    content = df_to_csv(df)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=buchhaltung.csv"},
    )


# ── GET routes (from database) ──
@router.get("/banana")
async def export_banana(
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    df = await _get_bookings_df(db, user.tenant_id, source)
    if df.empty:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    content = df_to_banana_tsv(df)
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=banana_import.txt"},
    )

@router.get("/excel")
async def export_excel(
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    df = await _get_bookings_df(db, user.tenant_id, source)
    if df.empty:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    content = df_to_styled_excel(df)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=buchhaltung.xlsx"},
    )

@router.get("/csv")
async def export_csv(
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    df = await _get_bookings_df(db, user.tenant_id, source)
    if df.empty:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    content = df_to_csv(df)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=buchhaltung.csv"},
    )

class EmailRequest(BaseModel):
    to_email: str
    subject: str = ""
    source: str | None = None


@router.post("/email")
async def send_email(
    body: EmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not is_email_configured():
        raise HTTPException(400, "E-Mail nicht konfiguriert.")
    df = await _get_bookings_df(db, user.tenant_id, body.source)
    if df.empty:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    ok, msg = send_bookkeeping_email(df, body.to_email, body.subject or None)
    if not ok:
        raise HTTPException(500, msg)
    return {"message": msg}

class EmailWithRowsRequest(BaseModel):
    to_email: str
    subject: str = ""
    rows: list[BuchungRowExport]


@router.post("/email/rows")
async def send_email_with_rows(body: EmailWithRowsRequest):
    if not is_email_configured():
        raise HTTPException(400, "E-Mail nicht konfiguriert. SMTP in .env prüfen.")
    if not body.rows:
        raise HTTPException(404, "Keine Buchungen vorhanden.")
    df = _rows_to_df(body.rows)
    ok, msg = send_bookkeeping_email(df, body.to_email, body.subject or None)
    if not ok:
        raise HTTPException(500, msg)
    return {"message": msg}
