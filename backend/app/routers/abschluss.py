"""Abschluss — /api/abschluss (B-66 Monatsabschluss-Check).

Read-only: the month either closes or it names what is missing. Nothing here
changes data, so there is nothing to approve.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.export_batch import ExportCheck
from app.schemas.monatsabschluss import MonthKpisOut, MonthListResponse, MonthReportResponse
from app.services.monatsabschluss import MonatsabschlussService, default_month, month_label

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
