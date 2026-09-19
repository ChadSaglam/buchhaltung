"""Lohn — /api/lohn (B-72).

Thin: validate → LohnService → schema. Two things happen only here.

``/vorschau`` and ``/abrechnen`` take the same body and return the same shape.
That is on purpose: the preview must be the payslip, not an approximation of it,
so the only difference between the two routes is whether a row and three
bookings are written. Anything computed differently in a preview is a bug
waiting for the day somebody trusts it.

Issuing is ``require_editor``; reading is not. A payslip is money leaving the
company, and it is also the one document in this app that cannot be undone.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_editor
from app.models.booking import Booking
from app.models.lohn_settings import LOHN_QUELLE
from app.models.lohnabrechnung import Lohnabrechnung
from app.models.mitarbeiter import Mitarbeiter
from app.models.user import User
from app.schemas.lohn import (
    AbrechnenResponse,
    AbrechnungListItem,
    AbrechnungListResponse,
    AbzugOut,
    BuchungOut,
    BvgHinweisOut,
    BvgPruefungOut,
    FreigabeRequest,
    LohnlaufOut,
    LohnlaufRequest,
    LohnSettingsOut,
    LohnSettingsUpdate,
    MitarbeiterCreate,
    MitarbeiterOut,
    MitarbeiterUpdate,
)
from app.services import bvg as bvg_service
from app.services import lohn_pdf
from app.services.audit_log import AuditLogService
from app.services.lohn import Lohnlauf, fehlende_settings
from app.services.lohn_service import LohnService
from app.services.rechnung import RechnungService

router = APIRouter(prefix="/api/lohn", tags=["lohn"])


def _settings_out(settings) -> LohnSettingsOut:
    missing = fehlende_settings(settings)
    return LohnSettingsOut(
        **LohnSettingsOut.model_validate(settings).model_dump(exclude={"fehlt", "bereit", "quelle", "wasserzeichen"}),
        fehlt=missing,
        bereit=not missing,
        quelle=LOHN_QUELLE,
        wasserzeichen=lohn_pdf.wasserzeichen(settings.freigegeben),
    )


def _lauf_out(
    person: Mitarbeiter,
    lauf: Lohnlauf,
    row: Lohnabrechnung | None = None,
) -> LohnlaufOut:
    return LohnlaufOut(
        mitarbeiter_id=person.id,
        mitarbeiter=person.anzeige_name,
        jahr=lauf.jahr,
        monat=lauf.monat,
        periode=lauf.periode,
        anteil=lauf.anteil,
        stunden=lauf.stunden,
        stundenlohn=lauf.stundenlohn,
        grundlohn=lauf.grundlohn,
        dreizehnter=lauf.dreizehnter,
        zulagen=lauf.zulagen,
        kinderzulagen=lauf.kinderzulagen,
        ahv_lohn=lauf.ahv_lohn,
        brutto=lauf.brutto,
        abzuege=[AbzugOut(**vars(a)) for a in lauf.abzuege],
        abzuege_total=lauf.abzuege_total,
        netto=lauf.netto,
        arbeitgeber=[AbzugOut(**vars(a)) for a in lauf.arbeitgeber],
        ag_total=lauf.ag_total,
        abrechnung_id=row.id if row else None,
        abgerechnet_am=row.abgerechnet_am if row else None,
    )


def _buchung_out(booking: Booking) -> BuchungOut:
    return BuchungOut(
        datum=booking.datum,
        beschreibung=booking.beschreibung,
        betrag=booking.betrag,
        kt_soll=booking.kt_soll,
        kt_haben=booking.kt_haben,
    )


async def _letterhead(db: AsyncSession, user: User) -> tuple[str, str]:
    """Company name and address for the PDF, from the invoice profile (B-68)."""
    profile = await RechnungService(db, user).profile()
    adresse = " ".join(
        part
        for part in [f"{profile.strasse} {profile.hausnummer}".strip(), f"{profile.plz} {profile.ort}".strip()]
        if part
    )
    return profile.name, adresse


# ── Einstellungen ────────────────────────────────────────────────────────────


@router.get("/settings", response_model=LohnSettingsOut)
async def settings(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> LohnSettingsOut:
    """The tenant's rates, and which compulsory ones are still missing."""
    out = _settings_out(await LohnService(db, user).settings())
    await db.commit()
    return out


@router.put("/settings", response_model=LohnSettingsOut)
async def update_settings(
    body: LohnSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> LohnSettingsOut:
    out = _settings_out(await LohnService(db, user).update_settings(body.model_dump(exclude_unset=True)))
    await db.commit()
    return out


@router.post("/settings/freigabe", response_model=LohnSettingsOut)
async def freigabe(
    body: FreigabeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> LohnSettingsOut:
    """Sign off the setup, which is what removes the watermark from the payslips.

    Its own endpoint rather than a field on the rate form: this says a person
    compared one real month against the previous payroll, and that must not be
    possible to assert by accident while editing a percentage.
    """
    service = LohnService(db, user)
    out = _settings_out(await service.freigeben(body.freigegeben))
    await AuditLogService(user.tenant_id, db).record(
        action="lohn.freigabe",
        actor_user_id=user.id,
        target_type="lohn_settings",
        target_id=user.tenant_id,
        detail={"freigegeben": body.freigegeben},
    )
    await db.commit()
    return out


# ── Mitarbeiter ──────────────────────────────────────────────────────────────


@router.get("/mitarbeiter", response_model=list[MitarbeiterOut])
async def mitarbeiter_liste(
    aktiv: bool = Query(default=False, description="Nur Mitarbeitende ohne Austrittsdatum."),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MitarbeiterOut]:
    rows = await LohnService(db, user).mitarbeiter_liste(inklusive_ausgetreten=not aktiv)
    return [MitarbeiterOut.model_validate(r) for r in rows]


@router.post("/mitarbeiter", response_model=MitarbeiterOut, status_code=201)
async def mitarbeiter_anlegen(
    body: MitarbeiterCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> MitarbeiterOut:
    person = await LohnService(db, user).mitarbeiter_anlegen(body.model_dump(exclude_unset=True))
    await AuditLogService(user.tenant_id, db).record(
        action="lohn.mitarbeiter.neu",
        actor_user_id=user.id,
        target_type="mitarbeiter",
        target_id=person.id,
        detail={"name": person.anzeige_name},
    )
    await db.commit()
    return MitarbeiterOut.model_validate(person)


@router.get("/mitarbeiter/{mitarbeiter_id}", response_model=MitarbeiterOut)
async def mitarbeiter(
    mitarbeiter_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MitarbeiterOut:
    return MitarbeiterOut.model_validate(await LohnService(db, user).mitarbeiter(mitarbeiter_id))


@router.put("/mitarbeiter/{mitarbeiter_id}", response_model=MitarbeiterOut)
async def mitarbeiter_aendern(
    mitarbeiter_id: int,
    body: MitarbeiterUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> MitarbeiterOut:
    person = await LohnService(db, user).mitarbeiter_aendern(mitarbeiter_id, body.model_dump(exclude_unset=True))
    await db.commit()
    return MitarbeiterOut.model_validate(person)


# ── Abrechnen ────────────────────────────────────────────────────────────────


@router.get("/bvg-pruefung", response_model=BvgPruefungOut)
async def bvg_pruefung(
    jahr: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BvgPruefungOut:
    """Die eingetragenen BVG-Beträge gegen das gesetzliche Minimum (B-72, Option C).

    Liest nur. Die Altersgutschrift auf der Abrechnung kommt weiterhin von der
    Pensionskasse; hier steht, wo sie dem Obligatorium widerspricht.
    """
    leute = await LohnService(db, user).mitarbeiter_liste(inklusive_ausgetreten=False)
    grenzen, aktuell = bvg_service.grenzen_fuer(jahr)
    hinweise = bvg_service.pruefen(list(leute), jahr)
    return BvgPruefungOut(
        jahr=jahr,
        grenzbetraege_jahr=grenzen.jahr,
        grenzbetraege_aktuell=aktuell,
        geprueft=len(leute),
        hinweise=[BvgHinweisOut(code=h.code, text=h.text, mitarbeiter_id=h.mitarbeiter_id) for h in hinweise],
    )


@router.post("/vorschau", response_model=LohnlaufOut)
async def vorschau(
    body: LohnlaufRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LohnlaufOut:
    """What this month would pay. Nothing is written and nothing is booked."""
    service = LohnService(db, user)
    person, lauf = await service.vorschau(
        body.mitarbeiter_id,
        body.jahr,
        body.monat,
        zulagen=body.zulagen,
        dreizehnter=body.dreizehnter,
        stunden=body.stunden,
    )
    out = _lauf_out(person, lauf)
    await db.commit()
    return out


@router.post("/abrechnen", response_model=AbrechnenResponse, status_code=201)
async def abrechnen(
    body: LohnlaufRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> AbrechnenResponse:
    """Issue the payslip and book it. The period can only be issued once."""
    service = LohnService(db, user)
    row, bookings, person, lauf = await service.abrechnen(
        body.mitarbeiter_id,
        body.jahr,
        body.monat,
        zulagen=body.zulagen,
        dreizehnter=body.dreizehnter,
        stunden=body.stunden,
    )
    await AuditLogService(user.tenant_id, db).record(
        action="lohn.abrechnung",
        actor_user_id=user.id,
        target_type="lohnabrechnung",
        target_id=row.id,
        detail={"periode": row.periode, "brutto": row.brutto, "netto": row.netto},
    )
    await db.commit()
    return AbrechnenResponse(
        abrechnung=_lauf_out(person, lauf, row),
        buchungen=[_buchung_out(b) for b in bookings],
    )


@router.get("/abrechnungen", response_model=AbrechnungListResponse)
async def abrechnungen(
    jahr: int | None = Query(default=None, ge=2000, le=2100),
    mitarbeiter_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AbrechnungListResponse:
    rows = await LohnService(db, user).abrechnungen(jahr=jahr, mitarbeiter_id=mitarbeiter_id)
    return AbrechnungListResponse(
        eintraege=[AbrechnungListItem.model_validate(r) for r in rows],
        brutto_total=sum(r.brutto for r in rows),
        netto_total=sum(r.netto for r in rows),
        ag_total=sum(r.ag_total for r in rows),
    )


@router.get("/abrechnungen/{abrechnung_id}/lohnabrechnung.pdf")
async def abrechnung_pdf(
    abrechnung_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """The payslip as a file — each deduction with the rate that produced it."""
    service = LohnService(db, user)
    row, person = await service.abrechnung(abrechnung_id)
    settings = await service.settings()
    firma, adresse = await _letterhead(db, user)
    content = lohn_pdf.abrechnung_pdf(row, person, firma=firma, firma_adresse=adresse, freigegeben=settings.freigegeben)
    await db.commit()
    name = f"Lohnabrechnung-{row.periode}-{person.name or person.id}.pdf".replace(" ", "-")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )


@router.get("/mitarbeiter/{mitarbeiter_id}/jahr/{jahr}.pdf")
async def jahr_pdf(
    mitarbeiter_id: int,
    jahr: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Twelve payslips added up — the figures a Lohnausweis is filled in from."""
    service = LohnService(db, user)
    person = await service.mitarbeiter(mitarbeiter_id)
    rows = await service.jahreslohn(mitarbeiter_id, jahr)
    settings = await service.settings()
    firma, adresse = await _letterhead(db, user)
    content = lohn_pdf.jahr_pdf(
        rows, person, jahr, firma=firma, firma_adresse=adresse, freigegeben=settings.freigegeben
    )
    await db.commit()
    name = f"Jahreszusammenzug-{jahr}-{person.name or person.id}.pdf".replace(" ", "-")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )
