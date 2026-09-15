"""Abschluss — /api/abschluss (B-66 Monatsabschluss-Check).

Read-only: the month either closes or it names what is missing. Nothing here
changes data, so there is nothing to approve.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.export_batch import ExportCheck
from app.schemas.monatsabschluss import MonthKpisOut, MonthListResponse, MonthReportResponse
from app.schemas.mwst import MwstReportResponse, QuarterListResponse, ZifferOut
from app.services.monatsabschluss import MonatsabschlussService, default_month, month_label
from app.services.mwst import (
    METHODE_EFFEKTIV,
    MwstService,
    copy_block,
    default_quarter,
    quarter_label,
    render_text,
)

router = APIRouter(prefix="/api/abschluss", tags=["abschluss"])


@router.get("/monate", response_model=MonthListResponse)
async def months(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MonthListResponse:
    service = MonatsabschlussService(db, user)
    monate = await service.months()
    aktuell = monate[0] if monate else default_month([])
    return MonthListResponse(
        monate=monate,
        labels={m: month_label(m) for m in monate},
        aktuell=aktuell,
    )


@router.get("/monat", response_model=MonthReportResponse)
async def monat(
    monat: str | None = Query(default=None, description="JJJJ-MM; leer = neuester Monat mit Daten"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MonthReportResponse:
    report = await MonatsabschlussService(db, user).report(monat)
    return MonthReportResponse(
        monat=report.monat,
        label=report.label,
        ready=report.ready,
        blockers=report.blockers,
        warnings=report.warnings,
        kpis=MonthKpisOut(**vars(report.kpis)),
        checks=[ExportCheck(**vars(c)) for c in report.checks],
    )


@router.get("/quartale", response_model=QuarterListResponse)
async def quarters(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuarterListResponse:
    quartale = await MwstService(db, user).quarters()
    aktuell = quartale[0] if quartale else default_quarter([])
    return QuarterListResponse(
        quartale=quartale,
        labels={q: quarter_label(q) for q in quartale},
        aktuell=aktuell,
    )


def _mwst_response(report) -> MwstReportResponse:
    return MwstReportResponse(
        quartal=report.quartal,
        zeitraum=report.zeitraum,
        methode=report.methode,
        satz=report.satz,
        buchungen=report.buchungen,
        ready=report.ready,
        blockers=report.blockers,
        zu_bezahlen=report.value("500"),
        guthaben=report.value("510"),
        ziffern=[ZifferOut(**vars(r)) for r in report.ziffern],
        checks=[ExportCheck(**vars(c)) for c in report.checks],
        copy_block=copy_block(report),
    )


@router.get("/mwst", response_model=MwstReportResponse)
async def mwst(
    quartal: str | None = Query(default=None, description="JJJJ-Qn; leer = neuestes Quartal mit Buchungen"),
    methode: str = Query(default=METHODE_EFFEKTIV, description="effektiv | saldo"),
    satz: float | None = Query(default=None, description="Saldosteuersatz in %, nur für methode=saldo"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MwstReportResponse:
    """Formular 200 aus den Buchungen — ein Entwurf, der vor dem Einreichen geprüft wird."""
    return _mwst_response(await MwstService(db, user).report(quartal, methode, satz))


@router.get("/mwst.txt")
async def mwst_text(
    quartal: str | None = None,
    methode: str = METHODE_EFFEKTIV,
    satz: float | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Dasselbe als Blatt zum Ausdrucken oder für den Treuhänder."""
    report = await MwstService(db, user).report(quartal, methode, satz)
    return Response(
        content=render_text(report),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="mwst_{report.quartal}.txt"'},
    )
