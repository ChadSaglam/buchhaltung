"""E-Mail-Eingang — /api/email (B-69).

Three doors into the same service: the owner's page (`GET`/`PUT`), a manual
*Jetzt abrufen* for the IMAP mailbox, and the server-to-server webhook for a
mail provider. The webhook carries no user, so it is guarded by a shared secret
and stays a 404 while that secret is unset — same shape as the platform events.
"""

from __future__ import annotations

import json
from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_editor
from app.models.email_message import STATUS_ABGELEHNT
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.email_intake import (
    AbrufResponse,
    AbsenderRequest,
    EmailEingangResponse,
    EmailMessageOut,
    MailSettingsOut,
    MailSettingsUpdate,
)
from app.services import email_intake as intake
from app.services.email_intake import EmailIntakeService, UnknownRecipient

router = APIRouter(prefix="/api/email", tags=["email"])

RAW_KEYS = ("raw", "RawEmail", "raw_email", "message", "mime")


async def _settings_out(db: AsyncSession, user: User, config) -> MailSettingsOut:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    return MailSettingsOut(
        adresse=intake.address_for(getattr(tenant, "slug", None)),
        aktiv=bool(config.enabled),
        allow_list=config.allow_list or "",
        absender=intake.parse_allow_list(config.allow_list or ""),
        bereit=intake.intake_enabled() and bool(getattr(tenant, "slug", None)),
        imap=intake.imap_configured(),
        webhook=bool(settings.EMAIL_INBOUND_SECRET),
    )


@router.get("/", response_model=EmailEingangResponse)
async def email_eingang(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EmailEingangResponse:
    """Address, rules and what the mailbox did lately."""
    from datetime import datetime

    service = EmailIntakeService(db)
    config = await service.settings_for(user.tenant_id)
    messages = await service.recent(user.tenant_id)
    await db.commit()

    since = datetime.now(UTC) - timedelta(hours=24)
    belege = sum(
        m.document_count
        for m in messages
        if m.created_at and m.created_at.replace(tzinfo=m.created_at.tzinfo or UTC) >= since
    )
    return EmailEingangResponse(
        einstellungen=await _settings_out(db, user, config),
        nachrichten=[EmailMessageOut.model_validate(m) for m in messages],
        belege_24h=belege,
        abgelehnt=sum(1 for m in messages if m.status == STATUS_ABGELEHNT),
    )


@router.put("/einstellungen", response_model=MailSettingsOut)
async def update_settings(
    body: MailSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> MailSettingsOut:
    service = EmailIntakeService(db)
    config = await service.settings_for(user.tenant_id)
    if body.aktiv is not None:
        config.enabled = body.aktiv
    if body.allow_list is not None:
        config.allow_list = "\n".join(intake.parse_allow_list(body.allow_list))
    await db.flush()
    out = await _settings_out(db, user, config)
    await db.commit()
    return out


@router.post("/absender", response_model=MailSettingsOut)
async def allow_sender(
    body: AbsenderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> MailSettingsOut:
    """One click on a rejected message: this sender may deliver from now on."""
    service = EmailIntakeService(db)
    config = await service.allow_sender(user.tenant_id, body.adresse)
    out = await _settings_out(db, user, config)
    await db.commit()
    return out


@router.post("/abrufen", response_model=AbrufResponse)
async def fetch_now(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_editor),
) -> AbrufResponse:
    """Fetch the mailbox now instead of waiting for the scheduler."""
    if not intake.imap_configured():
        raise HTTPException(409, "Kein Postfach konfiguriert (IMAP_HOST/USER/PASSWORD und EMAIL_INTAKE_DOMAIN).")
    import asyncio

    raws = await asyncio.to_thread(intake.fetch_unseen)
    service = EmailIntakeService(db)
    handled = 0
    skipped = 0
    for raw in raws:
        try:
            await service.deliver(raw)
            handled += 1
        except UnknownRecipient:
            skipped += 1
    await db.commit()
    hinweis = f"{skipped} Nachricht(en) gehörten zu keinem Mandanten." if skipped else ""
    return AbrufResponse(geholt=handled, hinweis=hinweis)


@router.post("/inbound", include_in_schema=False)
async def inbound(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Mail provider → here. Raw MIME in the body, or JSON carrying it."""
    secret = settings.EMAIL_INBOUND_SECRET
    if not secret:
        raise HTTPException(status_code=404, detail="Not Found")
    if request.headers.get("X-Mail-Secret", "") != secret:
        raise HTTPException(status_code=401, detail="Nicht berechtigt.")

    body = await request.body()
    raw = body
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            payload = json.loads(body)
            for key in RAW_KEYS:
                value = payload.get(key) if isinstance(payload, dict) else None
                if isinstance(value, str) and value:
                    raw = value.encode("utf-8", "replace")
                    break
        except ValueError as exc:
            raise HTTPException(400, "Body ist weder MIME noch gültiges JSON.") from exc

    try:
        message = await EmailIntakeService(db).deliver(raw)
    except UnknownRecipient as exc:
        await db.rollback()
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": str(exc)})
    await db.commit()
    return JSONResponse(
        status_code=202,
        content={"status": message.status, "documents": message.document_count, "reason": message.reason},
    )
