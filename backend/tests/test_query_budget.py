"""Query budgets (B-27).

An N+1 never fails a test. It just makes the request slower in proportion to how
much the tenant already has — which is why every one of them in this codebase
survived until somebody counted. So each B-27 fix is guarded by a *budget*: the
number of statements an endpoint may issue, asserted against a dataset large
enough that the old code would blow straight through it.

The budgets are deliberately a little loose (they count the auth lookup and any
framework chatter as well). They are there to catch a *shape* regression — a
SELECT that moved inside a loop — not to freeze an exact number.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event, select

from app.models.classifier_model import ClassifierModel
from app.services.classifier import TenantClassifier
from app.services.model_blob import pack, sha256_hex
from tests.factories import (
    auth_headers,
    create_booking,
    create_correction,
    create_memory,
    create_tenant,
    create_user,
)

pytestmark = pytest.mark.asyncio


class StatementCounter:
    """Counts the SQL an engine actually sends, by table."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def against(self, table: str) -> int:
        return sum(1 for s in self.statements if table in s.lower())

    def __len__(self) -> int:
        return len(self.statements)


@pytest.fixture
def counted(engine):
    counter = StatementCounter()

    def _record(conn, cursor, statement, parameters, context, executemany):
        counter.statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    yield counter
    event.remove(engine.sync_engine, "before_cursor_execute", _record)


# --------------------------------------------------------------------------- #
# GET /api/bookings/stats — was three statements over the same rows
# --------------------------------------------------------------------------- #


async def test_booking_stats_reads_the_bookings_table_once(client, db_session, counted):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    for i in range(12):
        await create_booking(db_session, tenant, betrag=10.0 + i, source="scanner" if i % 2 else "kontoauszug")

    counted.statements.clear()
    response = await client.get("/api/bookings/stats", headers=auth_headers(user))

    assert response.status_code == 200
    assert counted.against("bookings") == 1


async def test_booking_stats_still_returns_the_same_three_numbers(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await create_booking(db_session, tenant, betrag=10.10, source="scanner")
    await create_booking(db_session, tenant, betrag=20.20, source="scanner")
    await create_booking(db_session, tenant, betrag=30.30, source="kontoauszug")

    body = (await client.get("/api/bookings/stats", headers=auth_headers(user))).json()

    assert body["total_count"] == 3
    assert body["total_amount"] == 60.60
    assert body["by_source"] == {"scanner": 2, "kontoauszug": 1}


async def test_booking_stats_of_an_empty_tenant_is_zero_not_null(client, db_session):
    """`sum()` over no groups is 0, not None — the old code needed an `or 0` for this."""
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    body = (await client.get("/api/bookings/stats", headers=auth_headers(user))).json()

    assert body == {"total_count": 0, "total_amount": 0.0, "by_source": {}}


async def test_booking_stats_counts_a_missing_source_as_unknown(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await create_booking(db_session, tenant, betrag=5.0, source="")

    body = (await client.get("/api/bookings/stats", headers=auth_headers(user))).json()

    assert body["by_source"] == {"unknown": 1}


# --------------------------------------------------------------------------- #
# GET /api/stats/learning — the booking total was a query for a number it had
# --------------------------------------------------------------------------- #


async def test_learning_stats_does_not_count_bookings_twice(client, db_session, counted):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    for i in range(5):
        await create_booking(db_session, tenant, source="scanner" if i % 2 else "kontoauszug")

    counted.statements.clear()
    response = await client.get("/api/stats/learning", headers=auth_headers(user))

    assert response.status_code == 200
    # One histogram, and nothing else touching `bookings`.
    assert counted.against("from bookings") == 1


async def test_learning_stats_totals_are_unchanged(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await create_booking(db_session, tenant, source="scanner")
    await create_booking(db_session, tenant, source="scanner")
    await create_booking(db_session, tenant, source="kontoauszug")
    await create_memory(db_session, tenant, "Migros Zürich")
    await create_memory(db_session, tenant, "SBB Billett")
    await create_correction(db_session, tenant)

    body = (await client.get("/api/stats/learning", headers=auth_headers(user))).json()

    assert body["booking_count"] == 3
    assert body["memory_count"] == 2
    assert body["correction_count"] == 1
    assert sum(item["count"] for item in body["source_distribution"]) == body["booking_count"]


async def test_learning_stats_of_an_empty_tenant_is_all_zeroes(client, db_session):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    body = (await client.get("/api/stats/learning", headers=auth_headers(user))).json()

    assert body["booking_count"] == 0
    assert body["memory_count"] == 0
    assert body["correction_count"] == 0


# --------------------------------------------------------------------------- #
# POST /api/import — one SELECT per distinct description
# --------------------------------------------------------------------------- #


def _vendor(i: int) -> str:
    """A description that survives `make_memory_key`, which strips digits."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    return f"Lieferant {letters[i // 26]}{letters[i % 26]} AG"


def _banana_csv(rows: int) -> bytes:
    lines = ["Datum,Beschreibung,KtSoll,KtHaben,Betrag"]
    for i in range(rows):
        lines.append(f"15.03.2025,{_vendor(i)},6500,1020,{100 + i}.00")
    return "\n".join(lines).encode("utf-8")


async def test_import_looks_memory_up_once_not_once_per_description(client, db_session, counted):
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)

    counted.statements.clear()
    response = await client.post(
        "/api/import/banana?auto_train=false",
        headers=auth_headers(user),
        files={"file": ("buchungen.csv", _banana_csv(60), "text/csv")},
    )

    assert response.status_code == 200, response.text
    # 60 distinct descriptions. One chunked lookup, not sixty.
    assert counted.against("from memory") <= 2


async def test_import_still_upserts_instead_of_duplicating(client, db_session):
    """The preload has to *find* the existing rows, or the import would insert twice."""
    tenant = await create_tenant(db_session)
    user = await create_user(db_session, tenant)
    await create_memory(db_session, tenant, _vendor(0), kt_soll="9999")

    await client.post(
        "/api/import/banana?auto_train=false",
        headers=auth_headers(user),
        files={"file": ("buchungen.csv", _banana_csv(3), "text/csv")},
    )

    from app.models.memory import Memory

    rows = (await db_session.execute(select(Memory).where(Memory.tenant_id == tenant.id))).scalars().all()
    assert len(rows) == 3, "the seeded key must have been updated, not inserted again"
    updated = next(r for r in rows if r.kt_soll != "9999")
    assert updated.kt_soll == "6500"


# --------------------------------------------------------------------------- #
# The assistant context — was an unbounded scan on every chat message
# --------------------------------------------------------------------------- #


async def test_assistant_context_bounds_the_rows_it_reads(db_session):
    from app.services import ai_assistant

    tenant = await create_tenant(db_session)
    for i in range(30):
        await create_booking(db_session, tenant, betrag=float(i), datum=f"{(i % 28) + 1:02d}.03.2025")

    original = ai_assistant.KONTEXT_ZEILEN_MAX
    ai_assistant.KONTEXT_ZEILEN_MAX = 10
    try:
        context = await ai_assistant.build_context(tenant.id, db_session)
    finally:
        ai_assistant.KONTEXT_ZEILEN_MAX = original

    # The *stats* still cover everything — they are aggregated in SQL.
    assert context["stats"]["anzahl_buchungen"] == 30
    # The month buckets are built from the capped window.
    assert sum(m["anzahl"] for m in context["monatlich"]) == 10


async def test_assistant_context_issues_a_fixed_number_of_statements(db_session, counted):
    from app.services import ai_assistant

    tenant = await create_tenant(db_session)
    for i in range(25):
        await create_booking(db_session, tenant, betrag=float(i))

    counted.statements.clear()
    await ai_assistant.build_context(tenant.id, db_session)
    many = len(counted)

    tenant2 = await create_tenant(db_session)
    await create_booking(db_session, tenant2)
    counted.statements.clear()
    await ai_assistant.build_context(tenant2.id, db_session)
    few = len(counted)

    assert many == few, "the context must not issue more statements for a bigger tenant"


async def test_assistant_context_keeps_the_newest_months(db_session):
    from app.services import ai_assistant

    tenant = await create_tenant(db_session)
    await create_booking(db_session, tenant, datum="01.01.2025", betrag=1.0)
    await create_booking(db_session, tenant, datum="01.06.2025", betrag=2.0)

    context = await ai_assistant.build_context(tenant.id, db_session)

    assert [m["monat"] for m in context["monatlich"]] == ["2025-06", "2025-01"]


# --------------------------------------------------------------------------- #
# The classifier model — unpickled once per process, not once per request
# --------------------------------------------------------------------------- #


class _Stub:
    """Stands in for a fitted pipeline; only identity matters here."""

    def __init__(self, tag: str) -> None:
        self.tag = tag


async def _seed_model(db_session, tenant, tag: str) -> ClassifierModel:
    blob = pack(_Stub(tag))
    row = ClassifierModel(tenant_id=tenant.id, model_blob=blob, model_sha256=sha256_hex(blob))
    db_session.add(row)
    await db_session.flush()
    return row


async def test_a_second_classifier_reuses_the_unpickled_model(db_session, counted):
    from app.services import classifier as classifier_module

    classifier_module._MODEL_CACHE.clear()
    tenant = await create_tenant(db_session)
    await _seed_model(db_session, tenant, "first")

    first = await TenantClassifier(tenant.id, db_session)._load_model()
    counted.statements.clear()
    second = await TenantClassifier(tenant.id, db_session)._load_model()

    assert first is second, "the pipeline must be shared, not unpickled again"
    # Only the two small columns were read — the blob never left the database.
    assert counted.against("model_blob") == 0


async def test_retraining_invalidates_the_cached_model(db_session):
    from app.services import classifier as classifier_module

    classifier_module._MODEL_CACHE.clear()
    tenant = await create_tenant(db_session)
    row = await _seed_model(db_session, tenant, "first")

    first = await TenantClassifier(tenant.id, db_session)._load_model()

    new_blob = pack(_Stub("second"))
    row.model_blob = new_blob
    row.model_sha256 = sha256_hex(new_blob)
    await db_session.flush()

    second = await TenantClassifier(tenant.id, db_session)._load_model()

    assert first is not second
    assert second.tag == "second"


async def test_a_model_without_a_digest_is_never_cached(db_session):
    """Pre-B-34 rows carry no sha256, so the signature check must run every time."""
    from app.services import classifier as classifier_module

    classifier_module._MODEL_CACHE.clear()
    tenant = await create_tenant(db_session)
    row = ClassifierModel(tenant_id=tenant.id, model_blob=pack(_Stub("unsigned-row")), model_sha256=None)
    db_session.add(row)
    await db_session.flush()

    first = await TenantClassifier(tenant.id, db_session)._load_model()
    second = await TenantClassifier(tenant.id, db_session)._load_model()

    assert first is not None
    assert first is not second
    assert tenant.id not in classifier_module._MODEL_CACHE


async def test_the_model_cache_is_bounded(db_session):
    from app.services import classifier as classifier_module

    classifier_module._MODEL_CACHE.clear()
    for _ in range(classifier_module._MODEL_CACHE_MAX + 5):
        tenant = await create_tenant(db_session)
        await _seed_model(db_session, tenant, f"t{tenant.id}")
        await TenantClassifier(tenant.id, db_session)._load_model()

    assert len(classifier_module._MODEL_CACHE) == classifier_module._MODEL_CACHE_MAX


async def test_a_tenant_never_gets_another_tenants_model(db_session):
    from app.services import classifier as classifier_module

    classifier_module._MODEL_CACHE.clear()
    one = await create_tenant(db_session)
    two = await create_tenant(db_session)
    await _seed_model(db_session, one, "one")
    await _seed_model(db_session, two, "two")

    assert (await TenantClassifier(one.id, db_session)._load_model()).tag == "one"
    assert (await TenantClassifier(two.id, db_session)._load_model()).tag == "two"


async def test_a_tenant_without_a_model_gets_none(db_session):
    from app.services import classifier as classifier_module

    classifier_module._MODEL_CACHE.clear()
    tenant = await create_tenant(db_session)

    assert await TenantClassifier(tenant.id, db_session)._load_model() is None
