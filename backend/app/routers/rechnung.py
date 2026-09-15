"""Rechnungen schreiben — /api/rechnungen und /api/rechnungen/firma (B-68).

Thin layer: validate → RechnungService → schema. The only thing that happens
here and nowhere else is the print view, which is HTML on purpose (a real PDF
renderer is one dependency decision for every document — B-77).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_editor
from app.models.document import Document
from app.models.invoice_position import InvoicePosition
from app.models.user import User
from app.schemas.document import DocumentOut
from app.schemas.rechnung import (
    FirmaProfilOut,
    FirmaProfilUpdate,
    PositionOut,
    RechnungCreate,
    RechnungListItem,
    RechnungListResponse,
    RechnungOut,
)
from app.services import swiss_qr
from app.services.rechnung import PositionInput, RechnungService, totals_for

router = APIRouter(prefix="/api/rechnungen", tags=["rechnungen"])


def _profile_out(service: RechnungService, profile) -> FirmaProfilOut:
    missing = service.profile_ready(profile)
    referenz_typ = (
        swiss_qr.REFERENCE_QRR
        if swiss_qr.is_qr_iban(profile.iban)
        else swiss_qr.REFERENCE_SCOR
        if swiss_qr.is_valid_iban(profile.iban)
        else swiss_qr.REFERENCE_NON
    )
    return FirmaProfilOut(
        **FirmaProfilOut.model_validate(profile).model_dump(
            exclude={"iban_formatiert", "qr_iban", "referenz_typ", "fehlt", "bereit"}
        ),
        iban_formatiert=swiss_qr.format_iban(profile.iban),
        qr_iban=swiss_qr.is_qr_iban(profile.iban),
        referenz_typ=referenz_typ,
        fehlt=missing,
        bereit=not missing,
    )


def _positions_out(rows: list[InvoicePosition]) -> list[PositionOut]:
    return [
        PositionOut(
            position=row.position,
            bezeichnung=row.bezeichnung,
            menge=row.menge,
            einheit=row.einheit,
            einzelpreis=row.einzelpreis,
            betrag=round(float(row.menge or 0.0) * float(row.einzelpreis or 0.0), 2),
        )
        for row in rows
    ]


def _rechnung_out(
    doc: Document, rows: list[InvoicePosition], mwst_pct: str, *, booking_id: int | None = None
) -> RechnungOut:
    totals = totals_for(
        [PositionInput(bezeichnung=r.bezeichnung, menge=r.menge, einzelpreis=r.einzelpreis) for r in rows],
        mwst_pct,
    )
    reference_type = (
        swiss_qr.REFERENCE_QRR
        if swiss_qr.is_valid_qrr(doc.qr_reference)
        else (swiss_qr.REFERENCE_SCOR if doc.qr_reference else swiss_qr.REFERENCE_NON)
    )
    return RechnungOut(
        document=DocumentOut.model_validate(doc),
        positionen=_positions_out(rows),
        netto=totals.netto,
        mwst=totals.mwst,
        total=float(doc.amount or 0.0),
        referenz_typ=reference_type,
        referenz_formatiert=swiss_qr.format_reference(doc.qr_reference, reference_type),
        html_url=f"/api/rechnungen/{doc.id}/rechnung.html",
        booking_id=booking_id,
    )


@router.get("/firma", response_model=FirmaProfilOut)
async def firma(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> FirmaProfilOut:
    """Our own data. Empty on a fresh tenant — ``fehlt`` says what a QR-Rechnung still needs."""
    service = RechnungService(db, user)
    profile = await service.profile()
    await db.commit()
    return _profile_out(service, profile)


@router.put("/firma", response_model=FirmaProfilOut)
async def update_firma(
    body: FirmaProfilUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> FirmaProfilOut:
    service = RechnungService(db, user)
    profile = await service.update_profile(body.model_dump(exclude_unset=True))
    await db.commit()
    return _profile_out(service, profile)


@router.get("/", response_model=RechnungListResponse)
async def list_rechnungen(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RechnungListResponse:
    service = RechnungService(db, user)
    items = await service.list_invoices(limit)
    return RechnungListResponse(
        items=[RechnungListItem.model_validate(doc) for doc in items],
        count=len(items),
        naechste_nummer=await service.next_invoice_no(),
    )


@router.post("/", response_model=RechnungOut, status_code=201)
async def create_rechnung(
    body: RechnungCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> RechnungOut:
    """Kunde + Positionen → QR-Rechnung, Debitorenbuchung 1100/3000, offener Posten."""
    service = RechnungService(db, user)
    doc, rows, booking = await service.create(
        kunde=swiss_qr.Party(
            name=body.kunde.name,
            strasse=body.kunde.strasse,
            hausnummer=body.kunde.hausnummer,
            plz=body.kunde.plz,
            ort=body.kunde.ort,
            land=body.kunde.land,
        ),
        kunde_email=body.kunde.email,
        positions=[
            PositionInput(bezeichnung=p.bezeichnung, menge=p.menge, einheit=p.einheit, einzelpreis=p.einzelpreis)
            for p in body.positionen
        ],
        invoice_date=body.rechnungsdatum,
        due_date=body.faellig_am,
        bemerkung=body.bemerkung,
    )
    profile = await service.profile()
    await db.commit()
    # Server-side defaults (created_at/updated_at) are only known after the insert.
    await db.refresh(doc)
    return _rechnung_out(doc, rows, profile.mwst_pct, booking_id=booking.id)


@router.get("/{document_id}", response_model=RechnungOut)
async def get_rechnung(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RechnungOut:
    service = RechnungService(db, user)
    doc, rows = await service.own_invoice(document_id)
    profile = await service.profile()
    await db.commit()
    return _rechnung_out(doc, rows, profile.mwst_pct)


@router.get("/{document_id}/rechnung.html", response_class=HTMLResponse)
async def rechnung_page(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """The print-ready invoice with the Zahlteil (Strg/Cmd + P → PDF)."""
    service = RechnungService(db, user)
    page = await service.html(document_id)
    await db.commit()
    return HTMLResponse(page)
