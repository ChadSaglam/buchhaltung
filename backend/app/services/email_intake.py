"""E-Mail-Eingang — Belege kommen per Mail an (B-69).

The supplier already sends the invoice by e-mail; making the owner download it
and upload it again is work the machine should do. One mailbox serves the whole
deployment and the tenant is the ``+slug`` in the address:

    belege+muster-gmbh@rechnungen.example.ch

Two transports, one core: ``deliver()`` takes a raw MIME message — from the IMAP
poller or from an inbound webhook — and everything after that is identical.

Safe by default: an empty allow-list accepts **nothing**. The address is
guessable, so the first message from a new sender is recorded as *abgelehnt*
with the reason, and the owner allows that sender with one click. Better a
Beleg that arrives a day late than a booking made from spam.
"""

from __future__ import annotations

import asyncio
import contextlib
import email
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.email_message import (
    STATUS_ABGELEHNT,
    STATUS_FEHLER,
    STATUS_LEER,
    STATUS_VERARBEITET,
    EmailMessage,
)
from app.models.mail_settings import MailSettings
from app.models.tenant import Tenant
from app.models.user import User
from app.services.documents import DocumentService

logger = logging.getLogger(__name__)

RECIPIENT_HEADERS = ("Delivered-To", "X-Original-To", "X-Envelope-To", "To", "Cc")
DOCUMENT_TYPES = ("application/pdf",)
EXTENSION_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".gif": "image/gif",
}
MAX_ATTACHMENTS = 20


@dataclass
class Attachment:
    filename: str
    content_type: str
    content: bytes

    @property
    def usable(self) -> bool:
        return bool(self.content) and (self.content_type.startswith("image/") or self.content_type in DOCUMENT_TYPES)


@dataclass
class ParsedMail:
    message_id: str = ""
    from_addr: str = ""
    recipients: list[str] = field(default_factory=list)
    subject: str = ""
    sent_at: datetime | None = None
    attachments: list[Attachment] = field(default_factory=list)


# ── Adressen ─────────────────────────────────────────────────────────────────


def intake_enabled() -> bool:
    return bool(settings.EMAIL_INTAKE_DOMAIN)


def address_for(slug: str | None) -> str:
    """``belege+<slug>@<domain>`` — empty while the deployment has no intake domain."""
    if not slug or not intake_enabled():
        return ""
    return f"{settings.EMAIL_INTAKE_LOCALPART}+{slug}@{settings.EMAIL_INTAKE_DOMAIN}"


def slug_from_address(address: str) -> str | None:
    """The tenant slug out of one recipient address, or None when it is not ours."""
    address = (address or "").strip().lower()
    if "@" not in address or not intake_enabled():
        return None
    local, _, domain = address.partition("@")
    if domain != settings.EMAIL_INTAKE_DOMAIN.lower():
        return None
    prefix = f"{settings.EMAIL_INTAKE_LOCALPART.lower()}+"
    if not local.startswith(prefix):
        return None
    slug = local[len(prefix) :].strip()
    return slug or None


def slug_from_recipients(recipients: list[str]) -> str | None:
    for address in recipients:
        slug = slug_from_address(address)
        if slug:
            return slug
    return None


def parse_allow_list(raw: str) -> list[str]:
    """One entry per line or comma separated; addresses and ``@domain`` entries."""
    parts = re.split(r"[\n,;]+", raw or "")
    return [p.strip().lower() for p in parts if p.strip()]


def sender_allowed(from_addr: str, allow_list: str) -> bool:
    sender = (from_addr or "").strip().lower()
    if not sender:
        return False
    entries = parse_allow_list(allow_list)
    if not entries:
        return False  # safe by default: an empty list lets nothing in
    domain = sender.partition("@")[2]
    for entry in entries:
        if entry == sender:
            return True
        if entry.startswith("@") and domain == entry[1:]:
            return True
        if entry == "*":
            return True
    return False


# ── MIME ─────────────────────────────────────────────────────────────────────


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return value


def _content_type(part: Message, filename: str) -> str:
    declared = (part.get_content_type() or "").lower()
    if declared and declared != "application/octet-stream":
        return declared
    suffix = filename.lower().rsplit(".", 1)
    return EXTENSION_TYPES.get(f".{suffix[-1]}", declared) if len(suffix) == 2 else declared


def parse_message(raw: bytes) -> ParsedMail:
    """Raw MIME → the few facts the intake needs. Never raises on a broken mail."""
    message = email.message_from_bytes(raw)
    recipients = [
        addr.lower()
        for header in RECIPIENT_HEADERS
        for _name, addr in getaddresses(message.get_all(header, []))
        if addr
    ]
    from_addr = ""
    senders = getaddresses(message.get_all("From", []))
    if senders:
        from_addr = senders[0][1].lower()

    sent_at: datetime | None = None
    try:
        raw_date = message.get("Date")
        sent_at = parsedate_to_datetime(raw_date) if raw_date else None
        if sent_at and sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        sent_at = None

    attachments: list[Attachment] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = _decode(part.get_filename())
        disposition = (part.get_content_disposition() or "").lower()
        if not filename and disposition != "attachment":
            continue
        try:
            content = part.get_payload(decode=True) or b""
        except (AssertionError, ValueError, TypeError):
            continue
        name = filename or "anhang"
        attachments.append(Attachment(filename=name[:255], content_type=_content_type(part, name), content=content))
        if len(attachments) >= MAX_ATTACHMENTS:
            break

    return ParsedMail(
        message_id=(message.get("Message-ID") or "").strip()[:255],
        from_addr=from_addr,
        recipients=recipients,
        subject=_decode(message.get("Subject"))[:255],
        sent_at=sent_at,
        attachments=attachments,
    )


# ── Zustellung ───────────────────────────────────────────────────────────────


class UnknownRecipient(Exception):
    """No tenant behind the address — the caller decides whether that is a 404 or a shrug."""


class EmailIntakeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def settings_for(self, tenant_id: int) -> MailSettings:
        row = await self.db.execute(select(MailSettings).where(MailSettings.tenant_id == tenant_id))
        config = row.scalar_one_or_none()
        if config is None:
            config = MailSettings(tenant_id=tenant_id)
            self.db.add(config)
            await self.db.flush()
        return config

    async def _tenant_by_slug(self, slug: str) -> Tenant | None:
        row = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        return row.scalar_one_or_none()

    async def _actor(self, tenant_id: int) -> User | None:
        """Documents need an uploader; the tenant's oldest owner stands in for the mailbox."""
        rows = await self.db.execute(select(User).where(User.tenant_id == tenant_id).order_by(User.id))
        users = list(rows.scalars().all())
        for role in ("owner", "admin"):
            for user in users:
                if (user.role or "") == role:
                    return user
        return users[0] if users else None

    async def _seen(self, tenant_id: int, message_id: str) -> EmailMessage | None:
        if not message_id:
            return None
        row = await self.db.execute(
            select(EmailMessage).where(EmailMessage.tenant_id == tenant_id, EmailMessage.message_id == message_id)
        )
        return row.scalar_one_or_none()

    def _record(self, tenant_id: int, mail: ParsedMail, *, status: str, reason: str = "") -> EmailMessage:
        row = EmailMessage(
            tenant_id=tenant_id,
            message_id=mail.message_id,
            from_addr=mail.from_addr[:255],
            to_addr=(mail.recipients[0] if mail.recipients else "")[:255],
            subject=mail.subject,
            sent_at=mail.sent_at,
            status=status,
            reason=reason[:255],
            attachment_count=len(mail.attachments),
        )
        self.db.add(row)
        return row

    async def deliver(self, raw: bytes) -> EmailMessage:
        """One message in, one ``EmailMessage`` out — processed, rejected or empty."""
        mail = parse_message(raw)
        slug = slug_from_recipients(mail.recipients)
        if not slug:
            raise UnknownRecipient("Keine Empfängeradresse dieses Systems in der Nachricht.")
        tenant = await self._tenant_by_slug(slug)
        if tenant is None:
            raise UnknownRecipient(f"Kein Mandant mit dem Kürzel „{slug}“.")

        existing = await self._seen(tenant.id, mail.message_id)
        if existing is not None:
            logger.info("[MAIL] message %s already delivered to tenant %s", mail.message_id, tenant.id)
            return existing

        config = await self.settings_for(tenant.id)
        if not config.enabled:
            row = self._record(tenant.id, mail, status=STATUS_ABGELEHNT, reason="E-Mail-Eingang ist ausgeschaltet.")
            await self.db.flush()
            return row
        if not sender_allowed(mail.from_addr, config.allow_list):
            row = self._record(
                tenant.id,
                mail,
                status=STATUS_ABGELEHNT,
                reason=f"Absender {mail.from_addr or '(unbekannt)'} steht nicht auf der Liste.",
            )
            await self.db.flush()
            return row

        usable = [a for a in mail.attachments if a.usable]
        if not usable:
            row = self._record(
                tenant.id, mail, status=STATUS_LEER, reason="Keine Anhänge (PDF oder Bild) in der Nachricht."
            )
            await self.db.flush()
            return row

        actor = await self._actor(tenant.id)
        if actor is None:
            row = self._record(tenant.id, mail, status=STATUS_FEHLER, reason="Mandant hat keinen Benutzer.")
            await self.db.flush()
            return row

        service = DocumentService(self.db, actor)
        document_ids: list[int] = []
        failed: list[str] = []
        for attachment in usable:
            try:
                doc = await service.ingest(
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    content=attachment.content,
                )
                document_ids.append(doc.id)
            except HTTPException as exc:
                failed.append(f"{attachment.filename}: {exc.detail}")
                logger.info("[MAIL] attachment rejected (%s): %s", attachment.filename, exc.detail)

        row = self._record(
            tenant.id,
            mail,
            status=STATUS_VERARBEITET if document_ids else STATUS_FEHLER,
            reason="; ".join(failed),
        )
        row.document_count = len(document_ids)
        row.document_ids = ",".join(str(i) for i in document_ids)
        await self.db.flush()
        logger.info("[MAIL] tenant %s: %s Beleg(e) aus %s übernommen", tenant.id, len(document_ids), mail.from_addr)
        return row

    async def allow_sender(self, tenant_id: int, address: str) -> MailSettings:
        """Add one sender to the list — the one-click fix for a rejected message."""
        sender = (address or "").strip().lower()
        if not sender or "@" not in sender:
            raise HTTPException(400, "Das ist keine E-Mail-Adresse.")
        config = await self.settings_for(tenant_id)
        entries = parse_allow_list(config.allow_list)
        if sender not in entries:
            entries.append(sender)
        config.allow_list = "\n".join(entries)
        await self.db.flush()
        return config

    async def recent(self, tenant_id: int, limit: int = 20) -> list[EmailMessage]:
        rows = await self.db.execute(
            select(EmailMessage)
            .where(EmailMessage.tenant_id == tenant_id)
            .order_by(EmailMessage.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        return list(rows.scalars().all())


# ── IMAP ─────────────────────────────────────────────────────────────────────


def imap_configured() -> bool:
    return bool(settings.IMAP_HOST and settings.IMAP_USER and settings.IMAP_PASSWORD and intake_enabled())


def fetch_unseen(limit: int | None = None) -> list[bytes]:
    """Unread messages from the deployment mailbox, marked as read once fetched.

    Blocking (``imaplib``) on purpose — the caller runs it in a thread. Nothing
    is deleted: the mailbox stays the audit trail.
    """
    import imaplib

    batch = limit or settings.IMAP_BATCH
    raws: list[bytes] = []
    client = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
    try:
        client.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        client.select(settings.IMAP_FOLDER)
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            return []
        for num in (data[0].split() if data and data[0] else [])[:batch]:
            status, payload = client.fetch(num, "(RFC822)")
            if status != "OK" or not payload:
                continue
            for part in payload:
                if isinstance(part, tuple) and part[1]:
                    raws.append(part[1])
                    break
            client.store(num, "+FLAGS", "\\Seen")
    finally:
        with contextlib.suppress(Exception):  # a dead socket on logout is not our problem
            client.logout()
    return raws


async def poll_mailbox(session_factory) -> int:
    """Scheduler job: fetch what is unread and deliver it. Returns how many were handled."""
    if not imap_configured():
        return 0
    raws = await asyncio.to_thread(fetch_unseen)
    if not raws:
        return 0
    handled = 0
    async with session_factory() as session:
        service = EmailIntakeService(session)
        for raw in raws:
            try:
                await service.deliver(raw)
                handled += 1
            except UnknownRecipient as exc:
                logger.info("[MAIL] skipped: %s", exc)
            except Exception:
                logger.exception("[MAIL] delivery failed")
        await session.commit()
    return handled
