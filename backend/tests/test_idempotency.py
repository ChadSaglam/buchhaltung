"""B-52 — idempotency where it belongs: in the database, not in an ``if``.

Three races used to be winnable: two deliveries of the same `invoice.paid`,
two clicks on the same review item, and a client retrying a bulk booking POST
after a timeout. Each one is closed by a constraint or a conditional UPDATE,
and each test below is the race, not the happy path.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.booking import Booking
from app.models.correction import Correction
from app.models.idempotency_key import IdempotencyKey
from app.services.review_queue import ReviewQueueService
from tests.factories import auth_headers, create_review_item, create_tenant, create_user


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


# ── the billing booking ──────────────────────────────────────────────────────


async def test_two_billing_bookings_with_the_same_key_cannot_both_exist(db_session, actor):
    tenant, _user, _headers = actor
    key = "billing:invoice:42:paid"
    db_session.add(Booking(tenant_id=tenant.id, source="billing", source_key=key, betrag=100.0))
    await db_session.commit()

    db_session.add(Booking(tenant_id=tenant.id, source="billing", source_key=key, betrag=100.0))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_the_index_is_partial_so_ordinary_bookings_may_repeat_a_key(db_session, actor):
    """Two bookings from one receipt are normal — only billing keys are unique."""
    tenant, _user, _headers = actor
    key = "receipts/2026/abc.pdf"
    db_session.add(Booking(tenant_id=tenant.id, source="abgleich", source_key=key, betrag=10.0))
    db_session.add(Booking(tenant_id=tenant.id, source="abgleich", source_key=key, betrag=20.0))
    await db_session.commit()

    count = await db_session.scalar(select(func.count()).select_from(Booking).where(Booking.tenant_id == tenant.id))
    assert count == 2


async def test_another_tenant_may_use_the_same_billing_key(db_session, actor):
    tenant, _user, _headers = actor
    other = await create_tenant(db_session, name="Fremde AG")
    key = "billing:invoice:1:paid"
    db_session.add(Booking(tenant_id=tenant.id, source="billing", source_key=key, betrag=1.0))
    db_session.add(Booking(tenant_id=other.id, source="billing", source_key=key, betrag=1.0))
    await db_session.commit()  # different tenants, no conflict


# ── the review queue ─────────────────────────────────────────────────────────


async def test_approving_twice_trains_the_model_once(db_session, actor):
    tenant, _user, _headers = actor
    item = await create_review_item(db_session, tenant, beschreibung="Migros Zürich")
    service = ReviewQueueService(tenant.id, db_session)

    # 6500 is what the model predicted, so correcting to 4000 is a real correction.
    first = await service.approve(item.id, corrected_soll="4000")
    second = await service.approve(item.id, corrected_soll="6570")
    await db_session.commit()

    assert first is not None and first.status == "approved"
    assert second is None  # the second click finds nothing pending
    assert first.resolved_soll == "4000"

    corrections = await db_session.scalar(
        select(func.count()).select_from(Correction).where(Correction.tenant_id == tenant.id)
    )
    assert corrections == 1


async def test_rejecting_an_approved_item_does_nothing(db_session, actor):
    tenant, _user, _headers = actor
    item = await create_review_item(db_session, tenant)
    service = ReviewQueueService(tenant.id, db_session)

    assert await service.approve(item.id) is not None
    assert await service.reject(item.id) is None
    await db_session.commit()
    assert (await service._get_item(item.id)).status == "approved"


async def test_rejecting_once_works_and_is_final(db_session, actor):
    tenant, _user, _headers = actor
    item = await create_review_item(db_session, tenant)
    service = ReviewQueueService(tenant.id, db_session)

    rejected = await service.reject(item.id)
    assert rejected is not None and rejected.status == "rejected"
    assert rejected.resolved_at is not None
    assert await service.reject(item.id) is None


# ── the bulk POST ────────────────────────────────────────────────────────────


BOOKING = {"datum": "15.03.2026", "beschreibung": "Büromaterial", "betrag": 12.5, "kt_soll": "6500", "kt_haben": "1020"}


async def test_a_retried_post_with_the_same_key_books_once(client, db_session, actor):
    tenant, _user, headers = actor
    keyed = {**headers, "Idempotency-Key": "abc-123"}

    first = await client.post("/api/bookings/", headers=keyed, json=[BOOKING, BOOKING])
    second = await client.post("/api/bookings/", headers=keyed, json=[BOOKING, BOOKING])

    assert first.status_code == 200
    assert second.json() == first.json()  # the stored answer, not new rows

    count = await db_session.scalar(select(func.count()).select_from(Booking).where(Booking.tenant_id == tenant.id))
    assert count == 2


async def test_a_different_key_books_again(client, db_session, actor):
    tenant, _user, headers = actor
    await client.post("/api/bookings/", headers={**headers, "Idempotency-Key": "one"}, json=[BOOKING])
    await client.post("/api/bookings/", headers={**headers, "Idempotency-Key": "two"}, json=[BOOKING])

    count = await db_session.scalar(select(func.count()).select_from(Booking).where(Booking.tenant_id == tenant.id))
    assert count == 2


async def test_without_a_key_nothing_changes(client, db_session, actor):
    """No header, no promise — the old behaviour stays for every existing client."""
    tenant, _user, headers = actor
    await client.post("/api/bookings/", headers=headers, json=[BOOKING])
    await client.post("/api/bookings/", headers=headers, json=[BOOKING])

    count = await db_session.scalar(select(func.count()).select_from(Booking).where(Booking.tenant_id == tenant.id))
    assert count == 2


async def test_the_key_belongs_to_one_tenant(client, db_session, actor):
    _tenant, _user, headers = actor
    other_user = await create_user(db_session, await create_tenant(db_session, name="Fremde AG"), role="editor")
    other = {**auth_headers(other_user), "Idempotency-Key": "shared"}

    mine = await client.post("/api/bookings/", headers={**headers, "Idempotency-Key": "shared"}, json=[BOOKING])
    theirs = await client.post("/api/bookings/", headers=other, json=[BOOKING])

    assert mine.json()[0]["id"] != theirs.json()[0]["id"]
    keys = (await db_session.execute(select(IdempotencyKey.key))).scalars().all()
    assert keys.count("shared") == 2  # one row per tenant
