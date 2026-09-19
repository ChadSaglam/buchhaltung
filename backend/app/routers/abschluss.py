"""Abschluss — /api/abschluss (B-66 Monat, B-67 MWST, B-70 Jahr).

Read-only: eine Periode schliesst, oder sie sagt, was fehlt. Nichts hier ändert
Daten, also gibt es nichts zu bestätigen. Das Jahr kommt zusätzlich als PDF
(B-77, fpdf2) und als ZIP-Paket für den Treuhänder.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.export_batch import ExportCheck
from app.schemas.jahresabschluss import (
    AbschreibungOut,
    GruppeOut,
    JahrReportResponse,
    KontoPosition,
    YearListResponse,
)
from app.schemas.monatsabschluss import MonthKpisOut, MonthListResponse, MonthReportResponse
from app.schemas.mwst import MwstReportResponse, QuarterListResponse, ZifferOut
from app.services.jahresabschluss import Gruppe, JahresabschlussService, JahrReport, parse_year
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


# ── Jahr (B-70) ──────────────────────────────────────────────────────────────


def _gruppe(gruppe: Gruppe) -> GruppeOut:
    return GruppeOut(
        key=gruppe.key,
        label=gruppe.label,
        positionen=[KontoPosition(konto=p.konto, bezeichnung=p.bezeichnung, saldo=p.saldo) for p in gruppe.positionen],
        total=gruppe.total,
    )


def _jahr_response(report: JahrReport) -> JahrReportResponse:
    return JahrReportResponse(
        jahr=report.jahr,
        aktiven=_gruppe(report.aktiven),
        passiven=_gruppe(report.passiven),
        ertrag=[_gruppe(g) for g in report.ertrag],
        aufwand=[_gruppe(g) for g in report.aufwand],
        ertrag_total=report.ertrag_total,
        aufwand_total=report.aufwand_total,
        gewinn=report.gewinn,
        bilanz_differenz=report.bilanz_differenz,
        abschreibungen=[
            AbschreibungOut(
                konto=a.konto,
                bezeichnung=a.bezeichnung,
                buchwert=a.buchwert,
                satz=a.satz,
                betrag=a.betrag,
                quelle=a.quelle,
                kt_soll=a.kt_soll,
            )
            for a in report.abschreibungen
        ],
        abschreibungen_total=round(sum(a.betrag for a in report.abschreibungen), 2),
        checks=[
            ExportCheck(
                code=c.code,
                label=c.label,
                detail=c.detail,
                severity=c.severity,
                count=c.count,
                booking_ids=c.booking_ids,
            )
            for c in report.checks
        ],
        blockers=report.blockers,
        warnings=report.warnings,
        ready=report.ready,
        buchungen=report.buchungen,
        pdf_url=f"/api/abschluss/jahr.pdf?jahr={report.jahr}",
        paket_url=f"/api/abschluss/jahr.zip?jahr={report.jahr}",
    )


@router.get("/jahre", response_model=YearListResponse)
async def years(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> YearListResponse:
    from datetime import UTC, datetime

    jahre = await JahresabschlussService(db, user).years()
    return YearListResponse(jahre=jahre, aktuell=jahre[0] if jahre else datetime.now(UTC).year)


@router.get("/jahr", response_model=JahrReportResponse)
async def jahr(
    jahr: int | None = Query(default=None, description="Vierstellig, z. B. 2026"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JahrReportResponse:
    """Bilanz, Erfolgsrechnung, Abschreibungsvorschlag und Prüfliste eines Jahres."""
    service = JahresabschlussService(db, user)
    report = await service.report(parse_year(jahr, 0) if jahr is not None else None)
    return _jahr_response(report)


@router.get("/jahr.pdf")
async def jahr_pdf(
    jahr: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Der Abschluss als PDF — das, was der Treuhänder unterschreibt."""
    report, content = await JahresabschlussService(db, user).pdf(parse_year(jahr, 0) if jahr is not None else None)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="jahresabschluss-{report.jahr}.pdf"'},
    )


@router.get("/jahr.zip")
async def jahr_paket(
    jahr: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """PDF, Banana-Datei, Prüfliste und alle Belege des Jahres in einem ZIP."""
    report, content = await JahresabschlussService(db, user).paket(parse_year(jahr, 0) if jahr is not None else None)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="jahresabschluss-{report.jahr}.zip"'},
    )
