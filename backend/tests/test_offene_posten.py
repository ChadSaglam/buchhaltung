"""Offene Posten + Mahnung (B-65): aging, Debitor/Kreditor split, escalating draft, isolation."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.document import (
    DIRECTION_AUSGANG,
    DIRECTION_EINGANG,
    STATUS_BEZAHLT,
    STATUS_OFFEN,
    Document,
)
from app.services.offene_posten import (
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_OFFEN,
    BUCKET_OVER_90,
    DEFAULT_TERMS_DAYS,
    MAHNUNG_FRIST_DAYS,
    OffenePostenService,
    aging_bucket,
    build_items,
    days_overdue,
    effective_due_date,
    mahnstufe_label,
    mahnung_dateiname,
    mahnung_html,
    mahnung_pdf,
    mahnung_subject,
    mahnung_text,
    next_mahnstufe,
)
from tests.factories import auth_headers, create_tenant, create_user

TODAY = date(2026, 9, 15)


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


def doc(
    *,
    direction=DIRECTION_AUSGANG,
    amount=1000.0,
    due=None,
    invoice_date=None,
    status=STATUS_OFFEN,
    vendor="Kunde AG",
    no="R-2026-001",
    mahnstufe=0,
    email="",
    doc_id=1,
) -> Document:
    return Document(
        id=doc_id,
        tenant_id=1,
        status=status,
        direction=direction,
        file_key=f"receipts/1/{no}.pdf",
        filename=f"{no}.pdf",
        vendor=vendor,
        amount=amount,
        invoice_no=no,
        invoice_date=invoice_date,
        due_date=due,
        mahnstufe=mahnstufe,
        contact_email=email,
    )


# ── pure helpers ─────────────────────────────────────────────────────────────


def test_due_date_falls_back_to_invoice_date_plus_terms():
    assert effective_due_date(doc(due=date(2026, 9, 1))) == date(2026, 9, 1)
    assert effective_due_date(doc(invoice_date=date(2026, 8, 1))) == date(2026, 8, 1) + timedelta(
        days=DEFAULT_TERMS_DAYS
    )
    assert effective_due_date(doc()) is None


def test_days_overdue_is_zero_while_not_due_or_unknown():
    assert days_overdue(doc(due=date(2026, 9, 20)), TODAY) == 0
    assert days_overdue(doc(due=TODAY), TODAY) == 0
    assert days_overdue(doc(due=date(2026, 9, 5)), TODAY) == 10
    assert days_overdue(doc(), TODAY) == 0


def test_aging_buckets_cover_every_range():
    assert aging_bucket(0) == BUCKET_OFFEN
    assert aging_bucket(1) == BUCKET_1_30
    assert aging_bucket(30) == BUCKET_1_30
    assert aging_bucket(31) == BUCKET_31_60
    assert aging_bucket(61) == BUCKET_61_90
    assert aging_bucket(91) == BUCKET_OVER_90


def test_mahnstufe_escalates_but_stops_at_the_last_stage():
    assert next_mahnstufe(doc(mahnstufe=0)) == 1
    assert next_mahnstufe(doc(mahnstufe=2)) == 3
    assert next_mahnstufe(doc(mahnstufe=3)) == 3
    assert mahnstufe_label(1) == "Zahlungserinnerung"
    assert mahnstufe_label(2) == "1. Mahnung"
    assert mahnstufe_label(3) == "Letzte Mahnung"


def test_build_items_puts_the_longest_overdue_first():
    items = build_items(
        [
            doc(doc_id=1, due=date(2026, 9, 20)),
            doc(doc_id=2, due=date(2026, 6, 1)),
            doc(doc_id=3, due=date(2026, 9, 1)),
        ],
        TODAY,
    )
    assert [i.document.id for i in items] == [2, 3, 1]
    assert [i.days_overdue for i in items] == [106, 14, 0]
    assert [i.mahnbar for i in items] == [True, True, False]


def test_only_an_outgoing_invoice_is_mahnbar():
    items = build_items([doc(doc_id=7, direction=DIRECTION_EINGANG, due=date(2026, 6, 1))], TODAY)
    assert items[0].days_overdue > 0
    assert items[0].mahnbar is False


def test_stage_one_is_friendly_and_names_the_deadline():
    text = mahnung_text(doc(due=date(2026, 9, 1)), 1, company="Muster GmbH", today=TODAY)
    frist = (TODAY + timedelta(days=MAHNUNG_FRIST_DAYS)).strftime("%d.%m.%Y")
    assert "Guten Tag Kunde AG" in text
    assert "R-2026-001" in text
    assert "1'000.00" in text
    assert frist in text
    assert "Betreibung" not in text
    assert text.endswith("Muster GmbH\n")


def test_last_stage_names_the_consequence_once():
    text = mahnung_text(doc(due=date(2026, 5, 1)), 3, company="Muster GmbH", today=TODAY)
    assert "letzte Frist" in text
    assert "Art. 104 OR" in text
    assert "137 Tage überfällig" in text


def test_subject_follows_the_stage():
    assert mahnung_subject(doc(), 1) == "Zahlungserinnerung: Rechnung R-2026-001"
    assert mahnung_subject(doc(no=""), 2) == "1. Mahnung"


def test_html_letter_is_printable_and_escapes_the_customer_name():
    page = mahnung_html(doc(vendor="Meier & <Söhne>", due=date(2026, 9, 1)), 2, company="Muster GmbH", today=TODAY)
    assert page.startswith("<!doctype html>")
    assert "@page" in page and "A4" in page
    assert "Meier &amp; &lt;Söhne&gt;" in page
    assert "<script" not in page


def test_the_letter_is_also_a_file_a_scanner_never_sees():
    """A Mahnung goes in an envelope; "print the page" was never the answer."""
    import io

    content = mahnung_pdf(
        doc(due=date(2026, 9, 1)),
        2,
        company="Muster GmbH",
        company_address="Bahnhofstrasse 12, 8001 Zürich",
        today=TODAY,
    )
    assert content.startswith(b"%PDF-")

    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        assert len(pdf.pages) == 1
        text = pdf.pages[0].extract_text()

    assert "1. Mahnung" in text
    assert "Muster GmbH" in text
    assert "Bahnhofstrasse 12, 8001 Zürich" in text
    assert "R-2026-001" in text
    # The draft warning has to be on the file too, not only on the web page.
    assert "Entwurf" in text
    # One page in an envelope — a page number only asks what page two said.
    assert "Seite" not in text


def test_the_pdf_says_the_same_thing_as_the_html():
    """Two renderings of one letter; the day they disagree is the day one is wrong."""
    import io

    letter = doc(due=date(2026, 9, 1))
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(io.BytesIO(mahnung_pdf(letter, 3, company="Muster GmbH", today=TODAY))) as pdf:
        text = pdf.pages[0].extract_text()

    body = mahnung_text(letter, 3, company="Muster GmbH", today=TODAY)
    for sentence in ("letzte Frist", "Verzugszins", "gegenstandslos"):
        assert sentence in body
        assert sentence in text


def test_typographic_characters_do_not_kill_the_letter():
    content = mahnung_pdf(doc(vendor="Meier & „Söhne“ – AG"), 1, company="Muster GmbH – Zürich", today=TODAY)
    assert content.startswith(b"%PDF-")


def test_the_file_name_names_the_stage_and_the_invoice():
    assert mahnung_dateiname(doc(), 2) == "Mahnung-2-R-2026-001.pdf"
    assert mahnung_dateiname(doc(no="2026/07 A"), 1) == "Mahnung-1-2026-07-A.pdf"


# ── service + HTTP ───────────────────────────────────────────────────────────


async def add(db, tenant, **kw) -> Document:
    document = doc(**kw)
    document.id = None
    document.tenant_id = tenant.id
    db.add(document)
    await db.flush()
    return document


async def test_overview_splits_the_two_sides_with_totals_and_buckets(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant, direction=DIRECTION_AUSGANG, amount=1000.0, due=date(2026, 8, 1), no="D-1")
    await add(db_session, tenant, direction=DIRECTION_AUSGANG, amount=500.0, due=date(2026, 9, 30), no="D-2")
    await add(db_session, tenant, direction=DIRECTION_EINGANG, amount=200.0, due=date(2026, 9, 1), no="K-1")
    await add(
        db_session, tenant, direction=DIRECTION_AUSGANG, amount=999.0, status=STATUS_BEZAHLT, due=None, no="D-paid"
    )

    debitoren, kreditoren = await OffenePostenService(db_session, user).overview(TODAY)
    assert debitoren.count == 2
    assert debitoren.total == 1500.0
    assert debitoren.overdue_count == 1
    assert debitoren.overdue_total == 1000.0
    assert debitoren.buckets()[BUCKET_31_60] == 1000.0
    assert debitoren.buckets()[BUCKET_OFFEN] == 500.0
    assert kreditoren.count == 1
    assert kreditoren.overdue_total == 200.0


async def test_draft_refuses_a_supplier_invoice_and_a_paid_one(db_session, actor):
    tenant, user, _ = actor
    supplier = await add(db_session, tenant, direction=DIRECTION_EINGANG, due=date(2026, 8, 1), no="K-9")
    paid = await add(
        db_session, tenant, direction=DIRECTION_AUSGANG, status=STATUS_BEZAHLT, due=date(2026, 8, 1), no="D-9"
    )
    service = OffenePostenService(db_session, user)

    with pytest.raises(Exception) as supplier_exc:
        await service.draft(supplier.id)
    assert supplier_exc.value.status_code == 409
    assert "Debitoren" in str(supplier_exc.value.detail)

    with pytest.raises(Exception) as paid_exc:
        await service.draft(paid.id)
    assert paid_exc.value.status_code == 409


async def test_recording_a_mahnung_escalates_the_next_one(db_session, actor):
    tenant, user, _ = actor
    document = await add(db_session, tenant, due=date(2026, 7, 1), no="D-esc")
    service = OffenePostenService(db_session, user)

    _, first, _ = await service.record_mahnung(document.id)
    assert first == 1
    assert document.mahnstufe == 1
    assert document.mahnung_sent_at is not None

    _, second, _ = await service.record_mahnung(document.id)
    assert second == 2
    _, third, _ = await service.record_mahnung(document.id)
    _, fourth, _ = await service.record_mahnung(document.id)
    assert (third, fourth) == (3, 3)


async def test_http_overview_preview_letter_and_record(client, db_session, actor):
    tenant, _, headers = actor
    document = await add(db_session, tenant, due=date(2026, 7, 1), no="D-http", email="kunde@example.com")
    await db_session.commit()

    overview = await client.get("/api/offene-posten/", headers=headers)
    assert overview.status_code == 200
    body = overview.json()
    assert body["debitoren"]["count"] == 1
    assert body["debitoren"]["items"][0]["mahnbar"] is True
    assert body["debitoren"]["items"][0]["days_overdue"] > 0
    assert body["kreditoren"]["count"] == 0

    preview = await client.get(f"/api/offene-posten/{document.id}/mahnung", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["stufe"] == 1
    assert preview.json()["recorded"] is False
    assert preview.json()["empfaenger_email"] == "kunde@example.com"
    assert "Muster GmbH" in preview.json()["text"]

    letter = await client.get(f"/api/offene-posten/{document.id}/mahnung.html?stufe=2", headers=headers)
    assert letter.status_code == 200
    assert "1. Mahnung" in letter.text
    assert letter.headers["content-type"].startswith("text/html")

    recorded = await client.post(f"/api/offene-posten/{document.id}/mahnung", headers=headers, json={})
    assert recorded.status_code == 200
    assert recorded.json()["stufe"] == 1
    assert recorded.json()["recorded"] is True

    again = await client.get(f"/api/offene-posten/{document.id}/mahnung", headers=headers)
    assert again.json()["stufe"] == 2  # the next one escalates


async def test_a_document_can_be_marked_as_debitor_over_the_api(client, db_session, actor):
    tenant, _, headers = actor
    document = await add(db_session, tenant, direction=DIRECTION_EINGANG, due=date(2026, 7, 1), no="K-patch")
    await db_session.commit()

    patched = await client.patch(
        f"/api/documents/{document.id}",
        headers=headers,
        json={"direction": "ausgang", "contact_email": "kunde@example.com"},
    )
    assert patched.status_code == 200
    assert patched.json()["direction"] == "ausgang"
    assert patched.json()["contact_email"] == "kunde@example.com"
    assert (await client.get(f"/api/offene-posten/{document.id}/mahnung", headers=headers)).status_code == 200


async def test_the_letter_endpoint_serves_a_named_pdf(client, db_session, actor):
    tenant, _user, headers = actor
    document = await add(db_session, tenant, no="R-2026-009", due=date(2026, 8, 1))
    await db_session.commit()

    response = await client.get(f"/api/offene-posten/{document.id}/mahnung.pdf?stufe=2", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "Mahnung-2-R-2026-009.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")


async def test_the_letter_endpoint_refuses_another_tenants_invoice(client, db_session, actor):
    tenant, _user, _headers = actor
    document = await add(db_session, tenant, no="R-2026-010")
    await db_session.commit()

    other = await create_tenant(db_session, name="Fremd AG")
    other_user = await create_user(db_session, other, role="owner")
    response = await client.get(f"/api/offene-posten/{document.id}/mahnung.pdf", headers=auth_headers(other_user))
    assert response.status_code == 404


async def test_viewer_may_read_but_not_record(client, db_session, actor):
    tenant, _, _ = actor
    viewer = await create_user(db_session, tenant, role="viewer")
    document = await add(db_session, tenant, due=date(2026, 7, 1), no="D-role")
    await db_session.commit()
    headers = auth_headers(viewer)

    assert (await client.get("/api/offene-posten/", headers=headers)).status_code == 200
    assert (await client.get(f"/api/offene-posten/{document.id}/mahnung", headers=headers)).status_code == 200
    assert (await client.post(f"/api/offene-posten/{document.id}/mahnung", headers=headers)).status_code == 403


async def test_another_tenant_sees_nothing(client, db_session, actor):
    tenant, _, _ = actor
    document = await add(db_session, tenant, due=date(2026, 7, 1), no="D-iso")
    other_tenant = await create_tenant(db_session)
    other = await create_user(db_session, other_tenant, role="owner")
    await db_session.commit()
    other_headers = auth_headers(other)

    assert (await client.get("/api/offene-posten/", headers=other_headers)).json()["debitoren"]["count"] == 0
    assert (await client.get(f"/api/offene-posten/{document.id}/mahnung", headers=other_headers)).status_code == 404
    assert (
        await client.get(f"/api/offene-posten/{document.id}/mahnung.html", headers=other_headers)
    ).status_code == 404
    assert (await client.post(f"/api/offene-posten/{document.id}/mahnung", headers=other_headers)).status_code == 404
    assert (await client.get("/api/offene-posten/")).status_code == 401
