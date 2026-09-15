"""Offene Posten — /api/offene-posten (B-65).

The weekly question in two lists (wer schuldet uns / was schulden wir) plus a
Mahnung draft the owner reads, prints and sends themselves. Nothing is mailed
from here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_editor
from app.models.user import User
from app.schemas.document import DocumentOut
from app.schemas.offene_posten import (
    MahnungDraft,
    MahnungRequest,
    OffenePostenResponse,
    OpenItemOut,
    SideOut,
)
from app.services.offene_posten import (
    OffenePostenService,
    Side,
    mahnstufe_label,
    mahnung_html,
    mahnung_subject,
    mahnung_text,
)

router = APIRouter(prefix="/api/offene-posten", tags=["offene-posten"])


def _side(side: Side) -> SideOut:
    return SideOut(
        count=side.count,
        total=side.total,
        overdue_count=side.overdue_count,
        overdue_total=side.overdue_total,
        buckets=side.buckets(),
        items=[
            OpenItemOut(
                document=DocumentOut.model_validate(i.document),
                due_date=i.due_date,
                days_overdue=i.days_overdue,
                bucket=i.bucket,
                mahnbar=i.mahnbar,
            )
            for i in side.items
        ],
    )


def _draft(doc, stufe: int, company: str, *, recorded: bool = False) -> MahnungDraft:
    return MahnungDraft(
        document_id=doc.id,
        stufe=stufe,
        stufe_label=mahnstufe_label(stufe),
        empfaenger=doc.vendor or "",
        empfaenger_email=doc.contact_email or "",
        subject=mahnung_subject(doc, stufe),
        text=mahnung_text(doc, stufe, company=company),
        html_url=f"/api/offene-posten/{doc.id}/mahnung.html?stufe={stufe}",
        recorded=recorded,
    )


@router.get("/", response_model=OffenePostenResponse)
async def offene_posten(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OffenePostenResponse:
    debitoren, kreditoren = await OffenePostenService(db, user).overview()
    return OffenePostenResponse(debitoren=_side(debitoren), kreditoren=_side(kreditoren))


@router.get("/{document_id}/mahnung", response_model=MahnungDraft)
async def mahnung_preview(
    document_id: int,
    stufe: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MahnungDraft:
    """What the next Mahnung would say — a preview, nothing is stored."""
    doc, level, company = await OffenePostenService(db, user).draft(document_id, stufe)
    return _draft(doc, level, company)


@router.get("/{document_id}/mahnung.html", response_class=HTMLResponse)
async def mahnung_page(
    document_id: int,
    stufe: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """The print-ready letter (Strg/Cmd + P → PDF)."""
    doc, level, company = await OffenePostenService(db, user).draft(document_id, stufe)
    return HTMLResponse(mahnung_html(doc, level, company=company))


@router.post("/{document_id}/mahnung", response_model=MahnungDraft)
async def record_mahnung(
    document_id: int,
    body: MahnungRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> MahnungDraft:
    """The owner sent it — remember the stage so the next one escalates."""
    service = OffenePostenService(db, user)
    doc, level, company = await service.record_mahnung(document_id, body.stufe if body else None)
    await db.commit()
    return _draft(doc, level, company, recorded=True)
