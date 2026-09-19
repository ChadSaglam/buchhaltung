"""B-79 — die eigene Rechnung per E-Mail verschicken.

Der Kreis war bis hierher offen: Rechnung schreiben (B-68) und drucken (B-77)
ging, verschicken nicht. Was hier getestet wird, ist vor allem *wann nichts
passiert*: ohne Adresse, ohne SMTP, ohne Vorschau geht keine Mail raus.
"""

from __future__ import annotations

import datetime

import pytest

from app.models.company_profile import CompanyProfile
from app.models.document import DIRECTION_AUSGANG, DIRECTION_EINGANG, STATUS_OFFEN, Document
from app.models.invoice_position import InvoicePosition
from app.services import rechnung_versand
from app.services.email_sender import Attachment
from tests.factories import auth_headers, create_tenant, create_user

QR_IBAN = "CH4431999123000889012"


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


async def _profile(db, tenant, **overrides) -> CompanyProfile:
    profile = CompanyProfile(
        **{
            "tenant_id": tenant.id,
            "name": "Muster Informatik GmbH",
            "strasse": "Bahnhofstrasse",
            "hausnummer": "12",
            "plz": "8001",
            "ort": "Zürich",
            "iban": QR_IBAN,
            "email": "rechnung@muster.ch",
            "telefon": "044 123 45 67",
            "mwst_pct": "-8.10",
            **overrides,
        }
    )
    db.add(profile)
    await db.commit()
    return profile


async def _invoice(db, tenant, **overrides) -> Document:
    doc = Document(
        **{
            "tenant_id": tenant.id,
            "direction": DIRECTION_AUSGANG,
            "status": STATUS_OFFEN,
            "file_key": f"receipts/{tenant.id}/x.pdf",
            "filename": "x.pdf",
            "vendor": "Beispiel AG",
            "amount": 691.84,
            "currency": "CHF",
            "invoice_no": "2026-0001",
            "invoice_date": datetime.date(2026, 9, 16),
            "due_date": datetime.date(2026, 10, 16),
            "qr_reference": "210000000003139471430009017",
            "raw_json": '{"kunde": {"name": "Beispiel AG", "email": "buchhaltung@beispiel.ch"}, "referenz_typ": "QRR", "totals": {"netto": 640.0, "mwst": 51.84}}',
            **overrides,
        }
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    position = InvoicePosition(
        tenant_id=tenant.id,
        document_id=doc.id,
        position=1,
        bezeichnung="Beratung",
        menge=4,
        einheit="Std",
        einzelpreis=160.0,
    )
    db.add(position)
    await db.commit()
    return doc


class _Spy:
    """Stands in for the SMTP path: records the call, never opens a socket."""

    def __init__(self, ok: bool = True, message: str = "E-Mail gesendet") -> None:
        self.ok, self.message, self.calls = ok, message, []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.ok, self.message


# --- Adresse ----------------------------------------------------------------


def test_the_contact_on_the_document_wins_over_the_customer_block():
    doc = Document(contact_email="kontakt@beispiel.ch", raw_json='{"kunde": {"email": "alt@beispiel.ch"}}')
    assert rechnung_versand.empfaenger(doc) == "kontakt@beispiel.ch"


def test_the_customer_block_is_used_when_there_is_no_contact():
    doc = Document(contact_email="", raw_json='{"kunde": {"email": "alt@beispiel.ch"}}')
    assert rechnung_versand.empfaenger(doc) == "alt@beispiel.ch"


def test_a_broken_address_counts_as_no_address():
    """There is no customer master yet, so the invoice is the only source."""
    for bad in ("", "   ", "beispiel.ch", "a@b", "a b@c.ch", "@beispiel.ch"):
        doc = Document(contact_email=bad, raw_json="{}")
        assert rechnung_versand.empfaenger(doc) == "", bad


def test_unparsable_raw_json_does_not_raise():
    assert rechnung_versand.empfaenger(Document(contact_email="", raw_json="{not json")) == ""


# --- Text -------------------------------------------------------------------


def test_the_mail_says_what_it_is_and_what_to_do_with_it():
    profile = CompanyProfile(name="Muster GmbH", email="r@muster.ch", telefon="044 1")
    doc = Document(
        invoice_no="2026-0001",
        amount=691.84,
        currency="CHF",
        due_date=datetime.date(2026, 10, 16),
        vendor="Beispiel AG",
    )
    text = rechnung_versand.versand_text(doc, profile, reference="21 00000 00003", kunde_name="Beispiel AG")

    assert text.startswith("Guten Tag Beispiel AG")
    assert "691.84" in text
    assert "16.10.2026" in text
    assert "QR-Zahlteil" in text
    assert "21 00000 00003" in text
    assert text.rstrip().endswith("044 1 · r@muster.ch")
    assert "<" not in text and ">" not in text  # plain text, not HTML


def test_an_invoice_without_a_due_date_does_not_invent_one():
    text = rechnung_versand.versand_text(
        Document(invoice_no="1", amount=10.0, currency="CHF"), CompanyProfile(name="M")
    )
    assert "Zahlbar bis" not in text


def test_the_subject_names_the_invoice_and_the_sender():
    profile = CompanyProfile(name="Muster GmbH")
    assert rechnung_versand.versand_subject(Document(invoice_no="2026-0001"), profile) == (
        "Rechnung 2026-0001 von Muster GmbH"
    )
    assert rechnung_versand.versand_subject(Document(invoice_no=""), CompanyProfile(name="")) == "Rechnung"


# --- Entwurf ----------------------------------------------------------------


def test_the_draft_names_what_is_missing_instead_of_guessing():
    doc = Document(id=1, contact_email="", raw_json="{}", invoice_no="1", amount=1.0)
    draft = rechnung_versand.entwurf(doc, CompanyProfile(name=""), dateiname="R.pdf", mail_konfiguriert=False)
    assert draft.bereit is False
    assert "E-Mail-Adresse des Kunden" in draft.fehlt
    assert "Firmenname im Firmenprofil" in draft.fehlt
    assert any("SMTP" in item for item in draft.fehlt)


def test_a_complete_draft_is_ready():
    doc = Document(id=1, contact_email="k@beispiel.ch", raw_json="{}", invoice_no="1", amount=1.0)
    draft = rechnung_versand.entwurf(doc, CompanyProfile(name="Muster GmbH"), dateiname="R.pdf")
    assert draft.bereit is True
    assert draft.fehlt == []
    assert draft.dateiname == "R.pdf"


# --- HTTP -------------------------------------------------------------------


async def test_the_preview_sends_nothing(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    spy = _Spy()
    monkeypatch.setattr("app.routers.rechnung.send_message", spy)
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)

    body = (await client.get(f"/api/rechnungen/{doc.id}/versand", headers=headers)).json()
    assert body["empfaenger"] == "buchhaltung@beispiel.ch"
    assert "2026-0001" in body["subject"]
    assert body["dateiname"] == "Rechnung-2026-0001.pdf"
    assert body["bereit"] is True
    assert body["schon_gesendet_am"] == ""
    assert spy.calls == []


async def test_sending_attaches_the_pdf_and_remembers_the_date(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    spy = _Spy()
    monkeypatch.setattr("app.routers.rechnung.send_message", spy)
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)

    response = await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["empfaenger"] == "buchhaltung@beispiel.ch"

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["to_email"] == "buchhaltung@beispiel.ch"
    attachment: Attachment = call["attachments"][0]
    assert attachment.filename == "Rechnung-2026-0001.pdf"
    assert attachment.media_type == "application/pdf"
    assert attachment.content.startswith(b"%PDF-")
    assert call["reply_to"] == "rechnung@muster.ch"

    await db_session.refresh(doc)
    assert doc.sent_at is not None


async def test_the_owner_can_correct_the_address_in_the_preview(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    spy = _Spy()
    monkeypatch.setattr("app.routers.rechnung.send_message", spy)
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)

    await client.post(
        f"/api/rechnungen/{doc.id}/versand",
        json={"empfaenger": "neu@beispiel.ch", "subject": "Unsere Rechnung", "text": "Kurz und gut."},
        headers=headers,
    )
    call = spy.calls[0]
    assert call["to_email"] == "neu@beispiel.ch"
    assert call["subject"] == "Unsere Rechnung"
    assert call["text"] == "Kurz und gut."

    # The corrected address is kept, so the Mahnung later goes to the same place.
    await db_session.refresh(doc)
    assert doc.contact_email == "neu@beispiel.ch"


async def test_a_bad_address_is_refused_before_smtp(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant, raw_json='{"kunde": {"name": "Beispiel AG"}}')

    spy = _Spy()
    monkeypatch.setattr("app.routers.rechnung.send_message", spy)
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)

    response = await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=headers)
    assert response.status_code == 400
    assert spy.calls == []
    await db_session.refresh(doc)
    assert doc.sent_at is None


async def test_without_smtp_the_endpoint_says_so_instead_of_failing_later(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: False)
    response = await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=headers)
    assert response.status_code == 503


async def test_a_refused_send_leaves_the_invoice_unsent(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    monkeypatch.setattr("app.routers.rechnung.send_message", _Spy(ok=False, message="SMTP-Konfiguration prüfen."))
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)

    response = await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=headers)
    assert response.status_code == 502
    await db_session.refresh(doc)
    assert doc.sent_at is None


async def test_a_supplier_invoice_is_not_ours_to_send(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant, direction=DIRECTION_EINGANG)

    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)
    response = await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=headers)
    assert response.status_code in (404, 409)


async def test_a_viewer_may_preview_but_not_send(client, db_session, actor, monkeypatch):
    tenant, _user, _headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)
    viewer = await create_user(db_session, tenant, role="viewer")

    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)
    monkeypatch.setattr("app.routers.rechnung.send_message", _Spy())

    assert (await client.get(f"/api/rechnungen/{doc.id}/versand", headers=auth_headers(viewer))).status_code == 200
    assert (
        await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=auth_headers(viewer))
    ).status_code == 403


async def test_another_tenant_cannot_send_our_invoice(client, db_session, actor, monkeypatch):
    tenant, _user, _headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    other = await create_tenant(db_session, name="Fremd AG")
    other_user = await create_user(db_session, other, role="owner")
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)

    response = await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=auth_headers(other_user))
    assert response.status_code == 404


async def test_a_second_send_says_when_the_first_one_went(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    monkeypatch.setattr("app.routers.rechnung.send_message", _Spy())
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)

    await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=headers)
    draft = (await client.get(f"/api/rechnungen/{doc.id}/versand", headers=headers)).json()
    assert draft["schon_gesendet_am"] != ""


async def test_sending_is_written_to_the_audit_log(client, db_session, actor, monkeypatch):
    tenant, _user, headers = actor
    await _profile(db_session, tenant)
    doc = await _invoice(db_session, tenant)

    monkeypatch.setattr("app.routers.rechnung.send_message", _Spy())
    monkeypatch.setattr("app.routers.rechnung.is_email_configured", lambda: True)
    await client.post(f"/api/rechnungen/{doc.id}/versand", json={}, headers=headers)

    entries = (await client.get("/api/audit/", headers=headers)).json()["items"]
    assert any(e["action"] == "rechnung.versand" for e in entries)
