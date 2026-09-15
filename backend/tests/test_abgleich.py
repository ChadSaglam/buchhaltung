"""Abgleich API (phase 3): import lines, propose, confirm → bookings, reject, manual, isolation."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.models.bank_transaction import BankTransaction
from app.models.booking import Booking
from app.models.document import STATUS_BEZAHLT, STATUS_OFFEN, Document
from app.models.match import MATCH_ABGELEHNT, MATCH_BESTAETIGT, Match
from app.models.memory import Memory
from app.services.abgleich import AbgleichService, dedup_key, signed_amount
from tests.factories import auth_headers, create_tenant, create_user

QRR = "210000000003139471430009017"


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


async def add_document(
    db, tenant, *, amount: float, vendor="Lieferant AG", d="2026-04-01", ref="", soll="4000", haben="1020"
) -> Document:
    doc = Document(
        tenant_id=tenant.id,
        kind="rechnung",
        status=STATUS_OFFEN,
        file_key=f"receipts/{tenant.id}/{vendor}-{amount}.pdf",
        filename=f"{vendor}.pdf",
        vendor=vendor,
        amount=amount,
        currency="CHF",
        invoice_no="R-1",
        invoice_date=date.fromisoformat(d),
        due_date=None,
        qr_iban="",
        qr_reference=ref,
        qr_message="",
        extraction_source="qr" if ref else "vision",
        extraction_confidence=1.0,
        raw_json="",
        kt_soll=soll,
        kt_haben=haben,
        mwst_code="I81",
        mwst_pct="8.10",
        classification_confidence=0.9,
        error="",
    )
    db.add(doc)
    await db.flush()
    return doc


def rows(*items) -> list[dict]:
    """Parser-shaped statement rows (Belastung = money out)."""
    out = []
    for datum, text, belastung, gutschrift in items:
        out.append(
            {
                "Datum": datum,
                "Beschreibung": text,
                "Belastung": belastung,
                "Gutschrift": gutschrift,
                "Betrag CHF": gutschrift or belastung,
            }
        )
    return out


# ── row mapping ──────────────────────────────────────────────────────────────


def test_signed_amount_and_dedup_key():
    assert signed_amount({"Belastung": 770.60, "Gutschrift": None}) == -770.60
    assert signed_amount({"Belastung": None, "Gutschrift": 5945.50}) == 5945.50
    assert signed_amount({"Betrag CHF": 4.0}) == -4.0
    a = dedup_key(1, day=date(2026, 4, 2), amount=-1012.0, description="E-BANKING  SAMMELAUFTRAG")
    b = dedup_key(1, day=date(2026, 4, 2), amount=-1012.0, description="e-banking sammelauftrag")
    assert a == b  # whitespace and case are not a difference
    assert a != dedup_key(2, day=date(2026, 4, 2), amount=-1012.0, description="E-BANKING SAMMELAUFTRAG")


# ── import ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_persists_lines_and_skips_duplicates(db_session, actor):
    tenant, user, _headers = actor
    service = AbgleichService(db_session, user)
    statement = rows(
        ("02.04.2026", "E-BANKING-SAMMELAUFTRAG", 1012.00, None), ("07.04.2026", "GUTSCHRIFT", None, 5945.50)
    )

    first = await service.import_rows(statement, statement_key="receipts/x.pdf")
    assert (first.imported, first.duplicates) == (2, 0)
    second = await service.import_rows(statement)
    assert (second.imported, second.duplicates) == (0, 2)

    stored = (
        (await db_session.execute(select(BankTransaction).where(BankTransaction.tenant_id == tenant.id)))
        .scalars()
        .all()
    )
    assert len(stored) == 2
    by_amount = {round(t.amount, 2): t for t in stored}
    assert by_amount[-1012.00].value_date == date(2026, 4, 2)
    assert by_amount[5945.50].status == "offen"


# ── proposals + confirm ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reference_proposal_confirms_into_one_booking_and_teaches_memory(client, db_session, actor):
    tenant, user, headers = actor
    doc = await add_document(db_session, tenant, amount=1949.45, vendor="Cembra Money Bank AG", ref=QRR, soll="6260")
    service = AbgleichService(db_session, user)
    await service.import_rows(
        [
            {
                "Datum": "10.04.2026",
                "Beschreibung": "E-BANKING-AUFTRAG",
                "Belastung": 1949.45,
                "Gutschrift": None,
                "Referenz": QRR,
            }
        ]
    )
    await service.refresh_proposals()
    await db_session.commit()

    inbox = (await client.get("/api/abgleich/", headers=headers)).json()
    assert inbox["summary"] == {"vorschlaege": 1, "offene_zeilen": 0, "offene_dokumente": 0, "exakt": 1}
    item = inbox["items"][0]
    assert item["tier"] == "referenz" and item["score"] == 1.0
    assert "Referenz stimmt exakt" in item["reason"]
    assert item["documents"][0]["document"]["id"] == doc.id
    transaction_id = item["transaction"]["id"]

    decision = await client.post(f"/api/abgleich/{transaction_id}/confirm", headers=headers)
    assert decision.status_code == 200
    body = decision.json()
    assert body["status"] == "bestaetigt" and len(body["bookings"]) == 1

    booking = await db_session.get(Booking, body["bookings"][0])
    assert (booking.datum, booking.kt_soll, booking.kt_haben, booking.source) == (
        "10.04.2026",
        "6260",
        "1020",
        "abgleich",
    )
    assert booking.betrag == pytest.approx(1949.45)
    assert booking.mwst_amount == pytest.approx(146.07, abs=0.01)  # 1949.45 × 8.1/108.1, half-up

    await db_session.refresh(doc)
    assert doc.status == STATUS_BEZAHLT and doc.booking_id == booking.id
    tx = await db_session.get(BankTransaction, transaction_id)
    assert tx.status == "gebucht"
    # the confirmation is the training signal: vendor → account is remembered
    memory = (await db_session.execute(select(Memory).where(Memory.tenant_id == tenant.id))).scalars().all()
    assert any(m.kt_soll == "6260" for m in memory)
    assert (await client.get("/api/abgleich/", headers=headers)).json()["items"] == []


@pytest.mark.asyncio
async def test_sammelauftrag_confirms_into_one_booking_per_invoice(client, db_session, actor):
    tenant, user, headers = actor
    post = await add_document(db_session, tenant, amount=87.55, vendor="Die Post", soll="6513")
    other = await add_document(db_session, tenant, amount=924.45, vendor="Swisscom", soll="6510")
    service = AbgleichService(db_session, user)
    await service.import_rows(rows(("02.04.2026", "E-BANKING-SAMMELAUFTRAG", 1012.00, None)))
    await service.refresh_proposals()
    await db_session.commit()

    item = (await client.get("/api/abgleich/", headers=headers)).json()["items"][0]
    assert item["tier"] == "sammelauftrag" and item["is_split"] is True
    assert {d["document"]["id"] for d in item["documents"]} == {post.id, other.id}
    assert {d["amount"] for d in item["documents"]} == {87.55, 924.45}

    body = (await client.post(f"/api/abgleich/{item['transaction']['id']}/confirm", headers=headers)).json()
    assert len(body["bookings"]) == 2
    booked = [await db_session.get(Booking, b) for b in body["bookings"]]
    assert {b.kt_soll for b in booked} == {"6513", "6510"}
    assert sum(b.betrag for b in booked) == pytest.approx(1012.00)
    assert all(b.datum == "02.04.2026" for b in booked)
    tx = await db_session.get(BankTransaction, item["transaction"]["id"])
    assert tx.status == "zugeordnet"  # one line, two bookings → no single booking_id


@pytest.mark.asyncio
async def test_reject_is_remembered_and_the_pair_never_comes_back(client, db_session, actor):
    tenant, user, headers = actor
    doc = await add_document(db_session, tenant, amount=300.0, vendor="Swiss Life")
    service = AbgleichService(db_session, user)
    await service.import_rows(rows(("10.04.2026", "E-BANKING-AUFTRAG", 300.00, None)))
    await service.refresh_proposals()
    await db_session.commit()
    transaction_id = (await client.get("/api/abgleich/", headers=headers)).json()["items"][0]["transaction"]["id"]

    assert (await client.post(f"/api/abgleich/{transaction_id}/reject", headers=headers)).json()[
        "status"
    ] == "abgelehnt"
    await client.post("/api/abgleich/refresh", headers=headers)
    inbox = (await client.get("/api/abgleich/", headers=headers)).json()
    assert inbox["items"] == []
    assert inbox["summary"]["offene_zeilen"] == 1 and inbox["summary"]["offene_dokumente"] == 1

    match = (await db_session.execute(select(Match).where(Match.tenant_id == tenant.id))).scalars().one()
    assert match.status == MATCH_ABGELEHNT and match.decided_by == user.id and match.decided_at is not None
    await db_session.refresh(doc)
    assert doc.status == STATUS_OFFEN  # rejecting does not book anything


@pytest.mark.asyncio
async def test_manual_match_books_what_the_user_picked(client, db_session, actor):
    tenant, user, headers = actor
    doc = await add_document(db_session, tenant, amount=1234.55, vendor="Unbekannt GmbH", d="2026-01-02")
    service = AbgleichService(db_session, user)
    await service.import_rows(rows(("30.04.2026", "E-BANKING-SAMMELAUFTRAG", 1234.55, None)))
    await service.refresh_proposals()
    await db_session.commit()
    assert (await client.get("/api/abgleich/", headers=headers)).json()["items"] == []  # date too far apart

    transaction_id = (await client.get("/api/abgleich/", headers=headers)).json()["open_transactions"][0]["id"]
    body = (
        await client.post(
            f"/api/abgleich/{transaction_id}/manual", json={"document_ids": [doc.id, doc.id]}, headers=headers
        )
    ).json()
    assert len(body["bookings"]) == 1
    await db_session.refresh(doc)
    assert doc.status == STATUS_BEZAHLT
    match = (await db_session.execute(select(Match).where(Match.document_id == doc.id))).scalars().one()
    assert (match.tier, match.status) == ("manuell", MATCH_BESTAETIGT)


@pytest.mark.asyncio
async def test_ignore_takes_a_line_out_of_the_inbox(client, db_session, actor):
    _tenant, user, headers = actor
    service = AbgleichService(db_session, user)
    await service.import_rows(rows(("30.04.2026", "SALDO DIENSTLEISTUNGSPREISABSCHLUSS", 4.00, None)))
    await db_session.commit()
    transaction_id = (await client.get("/api/abgleich/", headers=headers)).json()["open_transactions"][0]["id"]

    assert (await client.post(f"/api/abgleich/{transaction_id}/ignore", headers=headers)).json()[
        "status"
    ] == "ignoriert"
    inbox = (await client.get("/api/abgleich/", headers=headers)).json()
    assert inbox["open_transactions"] == [] and inbox["summary"]["offene_zeilen"] == 0


@pytest.mark.asyncio
async def test_confirm_without_a_proposal_is_404(client, db_session, actor):
    _tenant, user, headers = actor
    service = AbgleichService(db_session, user)
    await service.import_rows(rows(("30.04.2026", "E-BANKING-AUFTRAG", 50.00, None)))
    await db_session.commit()
    transaction_id = (await client.get("/api/abgleich/", headers=headers)).json()["open_transactions"][0]["id"]
    assert (await client.post(f"/api/abgleich/{transaction_id}/confirm", headers=headers)).status_code == 404


# ── isolation and roles ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_another_tenant_sees_nothing_and_cannot_decide(client, db_session, actor):
    tenant, user, headers = actor
    await add_document(db_session, tenant, amount=100.0, vendor="Mein Lieferant")
    service = AbgleichService(db_session, user)
    await service.import_rows(rows(("05.04.2026", "E-BANKING-AUFTRAG", 100.00, None)))
    await service.refresh_proposals()
    await db_session.commit()
    transaction_id = (await client.get("/api/abgleich/", headers=headers)).json()["items"][0]["transaction"]["id"]

    intruder = await create_user(db_session, await create_tenant(db_session), role="owner")
    other = auth_headers(intruder)
    inbox = (await client.get("/api/abgleich/", headers=other)).json()
    assert inbox["items"] == [] and inbox["open_transactions"] == [] and inbox["open_documents"] == []
    assert (await client.post(f"/api/abgleich/{transaction_id}/confirm", headers=other)).status_code == 404
    assert (await client.post(f"/api/abgleich/{transaction_id}/reject", headers=other)).status_code == 404
    assert (await client.post(f"/api/abgleich/{transaction_id}/ignore", headers=other)).status_code == 404

    viewer = auth_headers(await create_user(db_session, tenant, role="viewer"))
    assert (await client.get("/api/abgleich/", headers=viewer)).status_code == 200
    assert (await client.post(f"/api/abgleich/{transaction_id}/confirm", headers=viewer)).status_code == 403
    assert (await client.post("/api/abgleich/refresh", headers=viewer)).status_code == 403
