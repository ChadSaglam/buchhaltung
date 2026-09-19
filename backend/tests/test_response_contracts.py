"""B-59 — the dict-returning endpoints now declare what they return.

Six endpoints used to hand back a bare `dict`, so FastAPI documented them as
`{}` and the frontend typed them by hand. Three of those hand-written shapes
had drifted (`/classify/info` claimed `sklearn_version`, `model_size_kb` and
`memory_size_kb`, none of which the endpoint has ever sent). These tests pin
both halves: the JSON the endpoint sends, and the schema the OpenAPI document
promises — because the frontend types are generated from the second one.
"""

from __future__ import annotations

import pytest

from app.main import app
from tests.factories import (
    auth_headers,
    create_audit_entry,
    create_booking,
    create_correction,
    create_konto,
    create_konto_default,
    create_memory,
    create_review_item,
    create_tenant,
    create_user,
)


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


def _schema_name(path: str, method: str) -> str:
    """The component the OpenAPI document promises for a 200 on `path`."""
    operation = app.openapi()["paths"][path][method]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    return ref.rsplit("/", 1)[-1]


def _properties(schema_name: str) -> dict:
    return app.openapi()["components"]["schemas"][schema_name]["properties"]


# --- /api/classify/info -----------------------------------------------------


async def test_classifier_info_is_documented_not_an_empty_dict(client, db_session, actor):
    _tenant, _user, headers = actor
    body = (await client.get("/api/classify/info", headers=headers)).json()

    assert set(body) == {
        "has_model",
        "model_trusted",
        "model_accuracy",
        "train_accuracy",
        "total_samples",
        "classes",
        "memory_count",
        "correction_count",
        "trained_at",
    }
    assert _schema_name("/api/classify/info", "get") == "ClassifierInfoResponse"


async def test_classifier_info_never_promised_the_three_invented_fields(client, actor):
    """The frontend interface carried them; the endpoint never sent them."""
    _tenant, _user, headers = actor
    body = (await client.get("/api/classify/info", headers=headers)).json()

    for invented in ("sklearn_version", "model_size_kb", "memory_size_kb"):
        assert invented not in body
        assert invented not in _properties("ClassifierInfoResponse")


# --- /api/bookings/stats ----------------------------------------------------


async def test_booking_stats_keeps_its_three_keys(client, db_session, actor):
    tenant, _user, headers = actor
    await create_booking(db_session, tenant, betrag=120.5, source="scanner")

    body = (await client.get("/api/bookings/stats", headers=headers)).json()
    assert set(body) == {"total_count", "total_amount", "by_source"}
    assert body["total_count"] == 1
    assert body["total_amount"] == 120.5
    assert body["by_source"] == {"scanner": 1}
    assert _schema_name("/api/bookings/stats", "get") == "BookingStatsResponse"


# --- /api/review/ -----------------------------------------------------------


async def test_the_review_queue_declares_its_item_shape(client, db_session, actor):
    tenant, _user, headers = actor
    await create_review_item(db_session, tenant, beschreibung="Unklar", betrag=42.0)

    body = (await client.get("/api/review/", headers=headers)).json()
    assert set(body) == {"threshold", "count", "items"}
    assert set(body["items"][0]) == {
        "id",
        "beschreibung",
        "betrag",
        "predicted_soll",
        "predicted_haben",
        "predicted_mwst_code",
        "predicted_mwst_pct",
        "confidence",
        "source",
        "status",
        "created_at",
    }
    assert _schema_name("/api/review/", "get") == "ReviewQueueResponse"


async def test_approve_and_reject_answer_with_a_status(client, db_session, actor):
    tenant, _user, headers = actor
    keep = await create_review_item(db_session, tenant)
    drop = await create_review_item(db_session, tenant)

    approved = await client.post(f"/api/review/{keep.id}/approve", json={}, headers=headers)
    rejected = await client.post(f"/api/review/{drop.id}/reject", headers=headers)

    assert approved.json() == {"status": "approved"}
    assert rejected.json() == {"status": "rejected"}
    assert _schema_name("/api/review/{item_id}/approve", "post") == "ReviewActionResponse"


# --- /api/audit/ ------------------------------------------------------------


async def test_the_audit_log_declares_its_entry_shape(client, db_session, actor):
    tenant, user, headers = actor
    await create_audit_entry(
        db_session,
        tenant,
        action="review.approve",
        actor_user_id=user.id,
        target_type="review_queue_item",
        target_id="7",
        detail={"resolved_soll": "6500"},
    )

    body = (await client.get("/api/audit/", headers=headers)).json()
    assert set(body) == {"count", "items"}
    entry = body["items"][0]
    assert set(entry) == {
        "id",
        "action",
        "actor_user_id",
        "target_type",
        "target_id",
        "detail",
        "created_at",
    }
    assert entry["detail"] == {"resolved_soll": "6500"}
    assert _schema_name("/api/audit/", "get") == "AuditListResponse"


# --- /api/stats/learning ----------------------------------------------------


async def test_learning_stats_separates_account_counts_from_source_counts(client, db_session, actor):
    tenant, _user, headers = actor
    await create_memory(db_session, tenant, "Migros Einkauf", kt_soll="6500")
    await create_correction(db_session, tenant, corrected_soll="4000")
    await create_booking(db_session, tenant, source="kontoauszug")

    body = (await client.get("/api/stats/learning", headers=headers)).json()
    assert set(body) == {
        "memory_count",
        "correction_count",
        "booking_count",
        "memory_distribution",
        "correction_distribution",
        "source_distribution",
    }
    assert body["memory_distribution"] == [{"account": "6500", "count": 1}]
    assert body["correction_distribution"] == [{"account": "4000", "count": 1}]
    assert body["source_distribution"] == [{"source": "kontoauszug", "count": 1}]
    assert _schema_name("/api/stats/learning", "get") == "LearningStatsResponse"


# --- /api/kontenplan/ -------------------------------------------------------


async def test_the_kontenplan_endpoints_are_documented(client, db_session, actor):
    tenant, _user, headers = actor
    await create_konto(db_session, tenant, konto_nr="6500", beschreibung="Büromaterial")
    await create_konto_default(db_session, tenant, konto_soll="6500", konto_haben="1020", mwst_code="V81")

    plan = (await client.get("/api/kontenplan/", headers=headers)).json()
    assert plan == {"kontenplan": {"6500": "Büromaterial"}}

    defaults = (await client.get("/api/kontenplan/defaults", headers=headers)).json()
    assert defaults == {"defaults": {"6500": {"KontoHaben": "1020", "MwStCode": "V81", "MwStUStProz": ""}}}

    saved = await client.put("/api/kontenplan/", json={"kontenplan": {"4000": "Warenaufwand"}}, headers=headers)
    assert saved.json() == {"status": "ok", "count": 1}

    assert _schema_name("/api/kontenplan/", "get") == "KontenplanResponse"
    assert _schema_name("/api/kontenplan/", "put") == "KontenplanSaved"
    assert _schema_name("/api/kontenplan/defaults", "get") == "KontoDefaultsResponse"


# --- the point of the exercise ---------------------------------------------


async def test_none_of_the_six_endpoints_returns_an_untyped_dict():
    """A bare `dict` return renders as `{}` in the schema — and generates `unknown`."""
    endpoints = [
        ("/api/classify/info", "get"),
        ("/api/bookings/stats", "get"),
        ("/api/review/", "get"),
        ("/api/audit/", "get"),
        ("/api/stats/learning", "get"),
        ("/api/kontenplan/", "get"),
        ("/api/kontenplan/defaults", "get"),
    ]
    for path, method in endpoints:
        assert _schema_name(path, method), f"{method.upper()} {path} has no response schema"
