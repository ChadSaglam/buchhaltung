"""Inbound platform events, receiver side (B-37, chadev-platform/contracts/events.md).

billing posts signed JSON to `/api/platform/events`; this module owns the
two halves the router needs:

* `verify_signature()` — HMAC-SHA256 over `f"{timestamp}.{raw body}"` with
  `PLATFORM_SHARED_SECRET`, constant-time compare, |now - ts| <= 5 min.
  Byte-for-byte the scheme billing's `services/events.py::sign` produces.
* `apply_invoice_paid()` — one booking `Bank (1020) an Debitoren (1100)`,
  idempotent on `bookings.source_key = "billing:invoice:<id>:paid"`.

Money arrives as a decimal *string* and is rounded half-up through the same
`round_chf()` every other booking uses (B-05); the stored amount is what the
invoice says, to the Rappen. Dates are stored as `DD.MM.YYYY` like every
booking in this app (the exports convert back to ISO).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.tenant import Tenant
from app.services.export import round_chf

SIGNATURE_PREFIX = "sha256="
MAX_SKEW_SECONDS = 5 * 60
SUPPORTED_VERSIONS = (1,)
EVENT_INVOICE_PAID = "invoice.paid"
BOOKING_SOURCE = "billing"
BANK_ACCOUNT = "1020"
DEBITOREN_ACCOUNT = "1100"


@dataclass(frozen=True)
class EventError(Exception):
    status_code: int
    code: str
    message: str


def sign(secret: str, timestamp: int, body: bytes) -> str:
    """`sha256=<hex HMAC-SHA256(secret, f"{timestamp}.{raw body}")>` — identical to billing."""
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_signature(
    secret: str, *, timestamp_header: str | None, signature_header: str | None, body: bytes, now: float | None = None
) -> None:
    """Raise `EventError` (401) on a stale timestamp or a signature mismatch."""
    try:
        timestamp = int(timestamp_header or "")
    except ValueError as exc:
        raise EventError(401, "bad_signature", "X-Platform-Timestamp fehlt oder ist ungültig") from exc
    if abs((now if now is not None else time.time()) - timestamp) > MAX_SKEW_SECONDS:
        raise EventError(401, "stale_timestamp", "X-Platform-Timestamp liegt ausserhalb des erlaubten Fensters")
    expected = sign(secret, timestamp, body)
    if not signature_header or not hmac.compare_digest(expected, signature_header.strip()):
        raise EventError(401, "bad_signature", "Signatur ungültig")


class _Client(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = ""


class _Invoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    number: str
    date: dt.date | None = None
    paid_at: dt.date
    currency: str = "CHF"
    # Decimal *string* on the wire; parsed here, never a float.
    total: str
    vat_total: str | None = None
    client: _Client
    payment_method: str | None = None
    payment_reference: str | None = None


class InvoicePaidEvent(BaseModel):
    """`invoice.paid` v1. Unknown fields are ignored (additive changes are free)."""

    model_config = ConfigDict(extra="ignore")

    event: str
    version: int
    tid: int = Field(strict=True)
    invoice: _Invoice


def parse_invoice_paid(payload: object) -> InvoicePaidEvent:
    if not isinstance(payload, dict):
        raise EventError(400, "invalid_payload", "Der Event-Body muss ein JSON-Objekt sein")
    version = payload.get("version")
    if version not in SUPPORTED_VERSIONS:
        raise EventError(400, "unsupported_version", f"Event-Version {version!r} wird nicht unterstützt")
    if payload.get("event") != EVENT_INVOICE_PAID:
        raise EventError(400, "unsupported_event", f"Event {payload.get('event')!r} wird nicht unterstützt")
    try:
        return InvoicePaidEvent.model_validate(payload)
    except ValidationError as exc:
        raise EventError(400, "invalid_payload", "Der Event-Body ist unvollständig oder ungültig") from exc


def source_key_for(invoice_id: int) -> str:
    return f"billing:invoice:{invoice_id}:paid"


def parse_amount(total: str) -> float:
    try:
        return float(round_chf(Decimal(total)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise EventError(400, "invalid_payload", "invoice.total ist kein gültiger Dezimalbetrag") from exc


async def resolve_tenant(db: AsyncSession, tid: int) -> Tenant:
    tenant = await db.scalar(select(Tenant).where(Tenant.platform_tenant_id == tid))
    if tenant is None:
        # Final for the sender (never retried): the tid has not done SSO yet.
        raise EventError(404, "unknown_tenant", "Kein Mandant für diese Plattform-Tenant-ID")
    return tenant


async def apply_invoice_paid(db: AsyncSession, tenant: Tenant, event: InvoicePaidEvent) -> bool:
    """Create the payment booking; returns False when it already exists (duplicate delivery)."""
    key = source_key_for(event.invoice.id)
    existing = await db.scalar(
        select(Booking.id).where(Booking.tenant_id == tenant.id, Booking.source_key == key).limit(1)
    )
    if existing is not None:
        return False
    invoice = event.invoice
    db.add(
        Booking(
            tenant_id=tenant.id,
            datum=invoice.paid_at.strftime("%d.%m.%Y"),
            beschreibung=f"Zahlung {invoice.number} {invoice.client.name}".strip(),
            betrag=parse_amount(invoice.total),
            kt_soll=BANK_ACCOUNT,
            kt_haben=DEBITOREN_ACCOUNT,
            mwst_code="",
            mwst_pct="",
            mwst_amount=0.0,
            beleg="",
            rechnung=invoice.number,
            source=BOOKING_SOURCE,
            source_key=key,
        )
    )
    await db.flush()
    return True
