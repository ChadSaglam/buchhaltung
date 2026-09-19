"""E-Mail-Eingang (B-69): Adressierung, Absenderliste, Zustellung, Isolation.

The rule that decides everything here: the address is guessable, so an empty
allow-list accepts nothing. Every test below is about what that costs and what
it buys.
"""

from __future__ import annotations

import io
from email.message import EmailMessage as MimeMessage

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.document import Document
from app.models.email_message import (
    STATUS_ABGELEHNT,
    STATUS_LEER,
    STATUS_VERARBEITET,
    EmailMessage,
)
from app.services import email_intake as intake
from app.services.email_intake import EmailIntakeService, UnknownRecipient
from tests.factories import auth_headers, create_tenant, create_user

DOMAIN = "rechnungen.example.ch"
LIEFERANT = "rechnung@lieferant.ch"


@pytest.fixture(autouse=True)
def intake_domain(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_INTAKE_DOMAIN", DOMAIN)
    monkeypatch.setattr(settings, "EMAIL_INTAKE_LOCALPART", "belege")
    return DOMAIN


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH", slug="muster-gmbh")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


def qr_png() -> bytes:
    """A real Swiss QR-bill image, so the ingest produces a clean document."""
    import segno

    from app.services import swiss_qr

    payload = swiss_qr.build_payload(
        iban="CH4431999123000889012",
        creditor=swiss_qr.Party(name="Lieferant AG", strasse="Werkstrasse", hausnummer="4", plz="3011", ort="Bern"),
        amount=250.0,
        reference_type="QRR",
        reference=swiss_qr.qrr_reference(1, 5),
    )
    buf = io.BytesIO()
    segno.make(payload, error="m").save(buf, kind="png", scale=6, border=4)
    return buf.getvalue()


def mail(
    *,
    to: str = f"belege+muster-gmbh@{DOMAIN}",
    sender: str = LIEFERANT,
    subject: str = "Rechnung September",
    message_id: str = "<1@lieferant.ch>",
    attachments: list[tuple[str, str, bytes]] | None = None,
    delivered_to: str | None = None,
) -> bytes:
    message = MimeMessage()
    message["From"] = f"Lieferant AG <{sender}>"
    message["To"] = to
    if delivered_to:
        message["Delivered-To"] = delivered_to
    message["Subject"] = subject
    message["Message-ID"] = message_id
    message["Date"] = "Tue, 15 Sep 2026 08:30:00 +0200"
    message.set_content("Guten Tag, anbei die Rechnung.")
    for filename, content_type, content in attachments or []:
        maintype, _, subtype = content_type.partition("/")
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    return message.as_bytes()


# ── Adressen und Regeln ──────────────────────────────────────────────────────


def test_the_address_carries_the_tenant():
    assert intake.address_for("muster-gmbh") == f"belege+muster-gmbh@{DOMAIN}"
    assert intake.slug_from_address(f"belege+muster-gmbh@{DOMAIN}") == "muster-gmbh"
    assert intake.slug_from_address(f"BELEGE+Muster-GmbH@{DOMAIN}".lower()) == "muster-gmbh"
    assert intake.slug_from_address(f"belege@{DOMAIN}") is None  # no tenant in it
    assert intake.slug_from_address("belege+muster-gmbh@fremde.ch") is None  # not our domain
    assert intake.slug_from_address("") is None


def test_without_a_domain_the_intake_is_off(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_INTAKE_DOMAIN", "")
    assert intake.intake_enabled() is False
    assert intake.address_for("muster-gmbh") == ""
    assert intake.slug_from_address(f"belege+muster-gmbh@{DOMAIN}") is None


def test_an_empty_allow_list_accepts_nothing():
    assert intake.sender_allowed(LIEFERANT, "") is False
    assert intake.sender_allowed(LIEFERANT, LIEFERANT) is True
    assert intake.sender_allowed(LIEFERANT, "@lieferant.ch") is True
    assert intake.sender_allowed(LIEFERANT, "@andere.ch") is False
    assert intake.sender_allowed("RECHNUNG@Lieferant.CH", "rechnung@lieferant.ch") is True
    assert intake.sender_allowed("", "@lieferant.ch") is False
    assert intake.parse_allow_list("a@b.ch\n@c.ch, d@e.ch") == ["a@b.ch", "@c.ch", "d@e.ch"]


def test_parsing_reads_sender_subject_and_attachments():
    raw = mail(attachments=[("rechnung.pdf", "application/pdf", b"%PDF-1.4 fake"), ("logo.gif", "image/gif", b"x")])
    parsed = intake.parse_message(raw)
    assert parsed.from_addr == LIEFERANT
    assert parsed.subject == "Rechnung September"
    assert f"belege+muster-gmbh@{DOMAIN}" in parsed.recipients
    assert [a.filename for a in parsed.attachments] == ["rechnung.pdf", "logo.gif"]
    assert parsed.attachments[0].content_type == "application/pdf"
    assert parsed.sent_at is not None


def test_routing_also_reads_the_delivered_to_header():
    raw = mail(to="buchhaltung@kunde.ch", delivered_to=f"belege+muster-gmbh@{DOMAIN}")
    parsed = intake.parse_message(raw)
    assert intake.slug_from_recipients(parsed.recipients) == "muster-gmbh"


# ── Zustellung ───────────────────────────────────────────────────────────────


async def test_an_unknown_recipient_is_not_our_mail(db_session, actor):
    service = EmailIntakeService(db_session)
    with pytest.raises(UnknownRecipient):
        await service.deliver(mail(to="jemand@anders.ch"))
    with pytest.raises(UnknownRecipient):
        await service.deliver(mail(to=f"belege+gibt-es-nicht@{DOMAIN}"))


async def test_an_unknown_sender_is_rejected_with_a_reason(db_session, actor):
    tenant, _user, _headers = actor
    service = EmailIntakeService(db_session)
    message = await service.deliver(mail(attachments=[("r.pdf", "application/pdf", b"%PDF-1.4")]))
    assert message.status == STATUS_ABGELEHNT
    assert LIEFERANT in message.reason
    assert message.document_count == 0
    documents = (await db_session.execute(select(Document).where(Document.tenant_id == tenant.id))).scalars().all()
    assert documents == []


async def test_an_allowed_sender_gets_the_beleg_into_the_system(db_session, actor):
    tenant, _user, _headers = actor
    service = EmailIntakeService(db_session)
    await service.allow_sender(tenant.id, LIEFERANT)

    message = await service.deliver(mail(attachments=[("rechnung.png", "image/png", qr_png())]))
    await db_session.commit()

    assert message.status == STATUS_VERARBEITET
    assert message.document_count == 1
    documents = (await db_session.execute(select(Document).where(Document.tenant_id == tenant.id))).scalars().all()
    assert len(documents) == 1
    doc = documents[0]
    assert doc.filename == "rechnung.png"
    assert doc.extraction_source == "qr"
    assert doc.amount == 250.0
    assert doc.vendor == "Lieferant AG"


async def test_a_whole_domain_can_be_allowed(db_session, actor):
    tenant, _user, _headers = actor
    service = EmailIntakeService(db_session)
    config = await service.settings_for(tenant.id)
    config.allow_list = "@lieferant.ch"
    await db_session.flush()

    message = await service.deliver(mail(attachments=[("rechnung.png", "image/png", qr_png())]))
    assert message.status == STATUS_VERARBEITET


async def test_the_same_message_is_never_ingested_twice(db_session, actor):
    tenant, _user, _headers = actor
    service = EmailIntakeService(db_session)
    await service.allow_sender(tenant.id, LIEFERANT)
    raw = mail(attachments=[("rechnung.png", "image/png", qr_png())])

    first = await service.deliver(raw)
    second = await service.deliver(raw)
    await db_session.commit()

    assert first.id == second.id
    documents = (await db_session.execute(select(Document).where(Document.tenant_id == tenant.id))).scalars().all()
    assert len(documents) == 1


async def test_a_mail_without_attachments_is_recorded_as_empty(db_session, actor):
    tenant, _user, _headers = actor
    service = EmailIntakeService(db_session)
    await service.allow_sender(tenant.id, LIEFERANT)
    message = await service.deliver(mail())
    assert message.status == STATUS_LEER
    assert "Anhänge" in message.reason


async def test_a_switched_off_intake_takes_nothing(db_session, actor):
    tenant, _user, _headers = actor
    service = EmailIntakeService(db_session)
    config = await service.settings_for(tenant.id)
    config.enabled = False
    config.allow_list = LIEFERANT
    await db_session.flush()

    message = await service.deliver(mail(attachments=[("r.png", "image/png", qr_png())]))
    assert message.status == STATUS_ABGELEHNT
    assert "ausgeschaltet" in message.reason


# ── API ──────────────────────────────────────────────────────────────────────


async def test_the_page_shows_the_address_and_what_arrived(client, db_session, actor):
    tenant, _user, headers = actor
    service = EmailIntakeService(db_session)
    await service.allow_sender(tenant.id, LIEFERANT)
    await service.deliver(mail(attachments=[("rechnung.png", "image/png", qr_png())]))
    await service.deliver(mail(sender="spam@fremd.ch", message_id="<2@fremd.ch>"))
    await db_session.commit()

    response = await client.get("/api/email/", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["einstellungen"]["adresse"] == f"belege+muster-gmbh@{DOMAIN}"
    assert body["einstellungen"]["absender"] == [LIEFERANT]
    assert body["einstellungen"]["bereit"] is True
    assert body["belege_24h"] == 1
    assert body["abgelehnt"] == 1
    assert len(body["nachrichten"]) == 2


async def test_settings_and_the_one_click_allow(client, db_session, actor):
    _tenant, _user, headers = actor
    saved = await client.put("/api/email/einstellungen", headers=headers, json={"allow_list": "a@b.ch, @c.ch"})
    assert saved.status_code == 200
    assert saved.json()["absender"] == ["a@b.ch", "@c.ch"]

    added = await client.post("/api/email/absender", headers=headers, json={"adresse": "Neu@Lieferant.CH"})
    assert added.status_code == 200
    assert "neu@lieferant.ch" in added.json()["absender"]

    off = await client.put("/api/email/einstellungen", headers=headers, json={"aktiv": False})
    assert off.json()["aktiv"] is False


async def test_a_viewer_may_look_but_not_change(client, db_session, actor):
    tenant, _user, _headers = actor
    viewer = await create_user(db_session, tenant, role="viewer")
    headers = auth_headers(viewer)
    assert (await client.get("/api/email/", headers=headers)).status_code == 200
    assert (await client.put("/api/email/einstellungen", headers=headers, json={"aktiv": False})).status_code == 403
    assert (await client.post("/api/email/absender", headers=headers, json={"adresse": "a@b.ch"})).status_code == 403


async def test_fetching_without_a_mailbox_says_so(client, actor):
    _tenant, _user, headers = actor
    response = await client.post("/api/email/abrufen", headers=headers)
    assert response.status_code == 409
    assert "Postfach" in response.json()["error"]["message"]


async def test_the_webhook_is_closed_without_a_secret(client, monkeypatch, actor):
    monkeypatch.setattr(settings, "EMAIL_INBOUND_SECRET", "")
    response = await client.post("/api/email/inbound", content=mail())
    assert response.status_code == 404


async def test_the_webhook_needs_the_right_secret(client, monkeypatch, actor):
    monkeypatch.setattr(settings, "EMAIL_INBOUND_SECRET", "s3cret")
    response = await client.post("/api/email/inbound", content=mail(), headers={"X-Mail-Secret": "falsch"})
    assert response.status_code == 401


async def test_the_webhook_delivers_like_the_mailbox(client, db_session, monkeypatch, actor):
    _tenant, _user, headers = actor
    monkeypatch.setattr(settings, "EMAIL_INBOUND_SECRET", "s3cret")
    await client.post("/api/email/absender", headers=headers, json={"adresse": LIEFERANT})

    raw = mail(attachments=[("rechnung.png", "image/png", qr_png())])
    response = await client.post("/api/email/inbound", content=raw, headers={"X-Mail-Secret": "s3cret"})
    assert response.status_code == 202
    assert response.json() == {"status": STATUS_VERARBEITET, "documents": 1, "reason": ""}

    ignored = await client.post(
        "/api/email/inbound", content=mail(to="fremd@anders.ch"), headers={"X-Mail-Secret": "s3cret"}
    )
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"


async def test_the_webhook_also_takes_json_from_a_provider(client, db_session, monkeypatch, actor):
    _tenant, _user, headers = actor
    monkeypatch.setattr(settings, "EMAIL_INBOUND_SECRET", "s3cret")
    await client.post("/api/email/absender", headers=headers, json={"adresse": LIEFERANT})

    raw = mail(attachments=[("rechnung.png", "image/png", qr_png())]).decode("utf-8", "replace")
    response = await client.post("/api/email/inbound", json={"RawEmail": raw}, headers={"X-Mail-Secret": "s3cret"})
    assert response.status_code == 202
    assert response.json()["documents"] == 1


async def test_another_tenant_sees_neither_messages_nor_senders(client, db_session, actor):
    tenant, _user, _headers = actor
    service = EmailIntakeService(db_session)
    await service.allow_sender(tenant.id, LIEFERANT)
    await service.deliver(mail(attachments=[("rechnung.png", "image/png", qr_png())]))
    await db_session.commit()

    other_tenant = await create_tenant(db_session, name="Fremde AG", slug="fremde-ag")
    other_user = await create_user(db_session, other_tenant, role="owner")
    other = auth_headers(other_user)

    body = (await client.get("/api/email/", headers=other)).json()
    assert body["nachrichten"] == []
    assert body["einstellungen"]["adresse"] == f"belege+fremde-ag@{DOMAIN}"
    assert body["einstellungen"]["absender"] == []

    mine = (await db_session.execute(select(EmailMessage).where(EmailMessage.tenant_id == tenant.id))).scalars().all()
    assert len(mine) == 1
