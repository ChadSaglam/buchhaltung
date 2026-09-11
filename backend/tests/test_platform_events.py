"""Inbound platform events (B-37, chadev-platform/contracts/events.md).

`deliver()` signs exactly like billing's `services/events.py::_attempt`
(canonical JSON, `X-Platform-*` headers, `sha256=<hex>` over
`f"{timestamp}.{raw body}"`), so the two sides cannot drift apart unnoticed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.booking import Booking
from tests.factories import create_tenant

pytestmark = pytest.mark.asyncio

SECRET = "platform-shared-secret-for-tests"
TID = 7


def invoice_paid(**overrides) -> dict:
    payload = {
        "event": "invoice.paid",
        "version": 1,
        "tid": TID,
        "invoice": {
            "id": 311,
            "number": "RE-2026-0042",
            "date": "2026-09-01",
            "paid_at": "2026-09-11",
            "currency": "CHF",
            "total": "1234.55",
            "vat_total": "88.45",
            "client": {"id": 12, "name": "Beispiel GmbH"},
            "payment_method": "bank",
            "payment_reference": "QRR 12345",
        },
    }
    payload.update(overrides)
    return payload


def encode_body(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def sign(secret: str, timestamp: int, body: bytes) -> str:
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def deliver(
    client, payload: dict, *, secret: str = SECRET, timestamp: int | None = None, body: bytes | None = None
):
    body = body if body is not None else encode_body(payload)
    timestamp = timestamp if timestamp is not None else int(time.time())
    headers = {
        "Content-Type": "application/json",
        "X-Platform-Event": payload.get("event", "invoice.paid"),
        "X-Platform-Delivery": str(uuid.uuid4()),
        "X-Platform-Timestamp": str(timestamp),
        "X-Platform-Signature": sign(secret, timestamp, body),
    }
    return await client.post("/api/platform/events", content=body, headers=headers)


@pytest.fixture
def platform_secret(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_SHARED_SECRET", SECRET)


@pytest.fixture
async def mirrored_tenant(db_session):
    tenant = await create_tenant(db_session, name="Muster AG")
    tenant.platform_tenant_id = TID
    await db_session.commit()
    return tenant


async def test_unset_secret_hides_the_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_SHARED_SECRET", None)
    resp = await deliver(client, invoice_paid())
    assert resp.status_code == 404


async def test_invoice_paid_creates_one_booking(client, db_session, platform_secret, mirrored_tenant):
    resp = await deliver(client, invoice_paid())
    assert resp.status_code == 202, resp.text
    assert resp.json() == {"status": "accepted"}

    rows = (await db_session.execute(select(Booking).where(Booking.tenant_id == mirrored_tenant.id))).scalars().all()
    assert len(rows) == 1
    booking = rows[0]
    assert booking.kt_soll == "1020"
    assert booking.kt_haben == "1100"
    assert booking.betrag == 1234.55
    assert booking.datum == "11.09.2026"
    assert booking.beschreibung == "Zahlung RE-2026-0042 Beispiel GmbH"
    assert booking.rechnung == "RE-2026-0042"
    assert booking.source == "billing"
    assert booking.source_key == "billing:invoice:311:paid"
    assert booking.mwst_code == "" and booking.mwst_amount == 0


async def test_amount_is_parsed_from_the_string_and_rounded_half_up(
    client, db_session, platform_secret, mirrored_tenant
):
    resp = await deliver(client, invoice_paid(invoice={**invoice_paid()["invoice"], "total": "2.675"}))
    assert resp.status_code == 202
    booking = await db_session.scalar(select(Booking).where(Booking.tenant_id == mirrored_tenant.id))
    assert booking.betrag == 2.68


async def test_duplicate_delivery_is_idempotent(client, db_session, platform_secret, mirrored_tenant):
    assert (await deliver(client, invoice_paid())).status_code == 202
    resp = await deliver(client, invoice_paid())
    assert resp.status_code == 200
    assert resp.json() == {"status": "duplicate"}
    count = len((await db_session.execute(select(Booking.id).where(Booking.tenant_id == mirrored_tenant.id))).all())
    assert count == 1


async def test_bad_signature_is_rejected(client, db_session, platform_secret, mirrored_tenant):
    resp = await deliver(client, invoice_paid(), secret="not-the-platform-secret")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "bad_signature"
    assert await db_session.scalar(select(Booking.id).limit(1)) is None


async def test_tampered_body_is_rejected(client, platform_secret, mirrored_tenant):
    payload = invoice_paid()
    body = encode_body(payload)
    timestamp = int(time.time())
    tampered = body.replace(b'"1234.55"', b'"9999.00"')
    headers = {
        "X-Platform-Event": "invoice.paid",
        "X-Platform-Delivery": str(uuid.uuid4()),
        "X-Platform-Timestamp": str(timestamp),
        "X-Platform-Signature": sign(SECRET, timestamp, body),
    }
    resp = await client.post("/api/platform/events", content=tampered, headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "bad_signature"


async def test_missing_headers_are_rejected(client, platform_secret, mirrored_tenant):
    resp = await client.post("/api/platform/events", content=encode_body(invoice_paid()))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "bad_signature"


async def test_stale_timestamp_is_rejected(client, platform_secret, mirrored_tenant):
    resp = await deliver(client, invoice_paid(), timestamp=int(time.time()) - 6 * 60)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "stale_timestamp"
    resp = await deliver(client, invoice_paid(), timestamp=int(time.time()) + 6 * 60)
    assert resp.status_code == 401


async def test_unknown_tenant_is_404(client, db_session, platform_secret):
    await create_tenant(db_session)  # a tenant that never did SSO
    resp = await deliver(client, invoice_paid())
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "unknown_tenant"


async def test_unsupported_version_is_400(client, platform_secret, mirrored_tenant):
    resp = await deliver(client, invoice_paid(version=2))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_version"


async def test_unsupported_event_is_400(client, platform_secret, mirrored_tenant):
    resp = await deliver(client, invoice_paid(event="invoice.unpaid"))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_event"


async def test_invalid_payload_is_400(client, platform_secret, mirrored_tenant):
    resp = await deliver(client, invoice_paid(invoice={"id": 1}))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_payload"
    resp = await deliver(client, {}, body=b"not json")
    assert resp.status_code == 400


async def test_bookings_land_in_the_right_tenant(client, db_session, platform_secret, mirrored_tenant):
    other = await create_tenant(db_session, name="Andere AG")
    other.platform_tenant_id = 8
    await db_session.commit()
    assert (await deliver(client, invoice_paid(tid=8))).status_code == 202
    mine = (await db_session.execute(select(Booking.id).where(Booking.tenant_id == mirrored_tenant.id))).all()
    theirs = (await db_session.execute(select(Booking.id).where(Booking.tenant_id == other.id))).all()
    assert len(mine) == 0 and len(theirs) == 1
