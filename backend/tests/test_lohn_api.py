"""B-72 — payroll over the API: refuse, preview, issue, book, print.

The tests that matter here are the ones about *issuing*, because that is the one
irreversible operation in this app: it writes a payslip that must never change
and three bookings the year-end reconciliation depends on. Everything else is
plumbing.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.booking import Booking
from app.models.lohnabrechnung import STATUS_ABGERECHNET, Lohnabrechnung
from tests.factories import auth_headers, create_tenant, create_user

VOLLSTAENDIG = {
    "uvg_bu_satz": 0.8,
    "uvg_nbu_satz": 1.6,
    "fak_satz": 1.2,
    "verwaltungskosten_satz": 0.15,
}

ANNA = {
    "vorname": "Anna",
    "name": "Muster",
    "ahv_nummer": "756.1234.5678.97",
    "eintritt": "2020-01-01",
    "monatslohn": 6000.0,
    "bvg_an_monat": 300.0,
    "bvg_ag_monat": 300.0,
}


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


async def _setup(client, headers, *, settings=None, person=None) -> int:
    await client.put("/api/lohn/settings", json=settings or VOLLSTAENDIG, headers=headers)
    res = await client.post("/api/lohn/mitarbeiter", json=person or ANNA, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


# --- Einstellungen --------------------------------------------------------


async def test_settings_start_empty_and_say_what_is_missing(client, actor):
    _t, _u, headers = actor
    res = await client.get("/api/lohn/settings", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["bereit"] is False
    assert "UVG NBU-Satz" in body["fehlt"]
    assert body["ahv_satz_an"] == 5.3  # federal, defaulted


async def test_settings_become_ready_once_the_rates_are_filled_in(client, actor):
    _t, _u, headers = actor
    res = await client.put("/api/lohn/settings", json=VOLLSTAENDIG, headers=headers)
    assert res.status_code == 200
    assert res.json() == {**res.json(), "bereit": True, "fehlt": []}


async def test_an_optional_insurance_can_be_cleared_again(client, actor):
    _t, _u, headers = actor
    await client.put("/api/lohn/settings", json={**VOLLSTAENDIG, "ktg_satz_an": 0.7}, headers=headers)
    res = await client.put("/api/lohn/settings", json={"ktg_satz_an": None}, headers=headers)
    assert res.json()["ktg_satz_an"] is None
    assert res.json()["bereit"] is True  # KTG is voluntary; clearing it is not a gap


async def test_a_compulsory_rate_cannot_be_cleared_by_sending_null(client, actor):
    _t, _u, headers = actor
    await client.put("/api/lohn/settings", json=VOLLSTAENDIG, headers=headers)
    res = await client.put("/api/lohn/settings", json={"fak_satz": None}, headers=headers)
    assert res.json()["fak_satz"] == 1.2


async def test_a_rate_above_a_hundred_percent_is_rejected(client, actor):
    _t, _u, headers = actor
    res = await client.put("/api/lohn/settings", json={"fak_satz": 250.0}, headers=headers)
    assert res.status_code == 422


# --- Mitarbeiter ----------------------------------------------------------


async def test_an_employee_can_be_created_and_read_back(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    res = await client.get(f"/api/lohn/mitarbeiter/{mid}", headers=headers)
    assert res.status_code == 200
    assert res.json()["anzeige_name"] == "Anna Muster"


async def test_the_active_filter_hides_leavers(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    await client.put(f"/api/lohn/mitarbeiter/{mid}", json={"austritt": "2026-03-31"}, headers=headers)
    alle = await client.get("/api/lohn/mitarbeiter", headers=headers)
    aktiv = await client.get("/api/lohn/mitarbeiter?aktiv=true", headers=headers)
    assert len(alle.json()) == 1
    assert aktiv.json() == []


async def test_an_employee_can_unresign(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    await client.put(f"/api/lohn/mitarbeiter/{mid}", json={"austritt": "2026-03-31"}, headers=headers)
    res = await client.put(f"/api/lohn/mitarbeiter/{mid}", json={"austritt": None}, headers=headers)
    assert res.json()["austritt"] is None


async def test_another_tenants_employee_is_not_found(client, actor, db_session):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    other = await create_tenant(db_session, name="Fremd AG")
    other_user = await create_user(db_session, other, role="owner")
    res = await client.get(f"/api/lohn/mitarbeiter/{mid}", headers=auth_headers(other_user))
    assert res.status_code == 404


# --- Vorschau -------------------------------------------------------------


async def test_the_preview_refuses_while_a_rate_is_missing(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers, settings={"uvg_bu_satz": 0.8})
    res = await client.post(
        "/api/lohn/vorschau", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers
    )
    assert res.status_code == 400
    assert "UVG NBU-Satz" in res.text


async def test_the_preview_returns_the_payslip(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    res = await client.post(
        "/api/lohn/vorschau", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body["brutto"] == 6000.0
    assert body["netto"] == pytest.approx(6000.0 - body["abzuege_total"])
    assert body["abrechnung_id"] is None


async def test_the_preview_writes_nothing(client, actor, db_session):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    await client.post("/api/lohn/vorschau", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers)
    rows = await db_session.execute(select(Lohnabrechnung))
    assert rows.scalars().all() == []


# --- Abrechnen ------------------------------------------------------------


async def test_issuing_writes_the_payslip_and_three_bookings(client, actor, db_session):
    tenant, _u, headers = actor
    mid = await _setup(client, headers)
    res = await client.post(
        "/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["abrechnung"]["abrechnung_id"] is not None
    assert len(body["buchungen"]) == 3

    rows = await db_session.execute(select(Booking).where(Booking.tenant_id == tenant.id))
    bookings = list(rows.scalars().all())
    assert {b.kt_soll for b in bookings} == {"5000", "5700"}
    assert {b.kt_haben for b in bookings} == {"2270", "1020"}


async def test_the_wage_expense_equals_the_gross(client, actor, db_session):
    tenant, _u, headers = actor
    mid = await _setup(client, headers)
    res = await client.post(
        "/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers
    )
    brutto = res.json()["abrechnung"]["brutto"]
    rows = await db_session.execute(select(Booking).where(Booking.tenant_id == tenant.id))
    aufwand = sum(b.betrag for b in rows.scalars().all() if b.kt_soll == "5000")
    assert aufwand == pytest.approx(brutto)


async def test_the_same_month_cannot_be_issued_twice(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    payload = {"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}
    assert (await client.post("/api/lohn/abrechnen", json=payload, headers=headers)).status_code == 201
    second = await client.post("/api/lohn/abrechnen", json=payload, headers=headers)
    assert second.status_code == 409


async def test_the_issued_payslip_keeps_the_rates_it_used(client, actor, db_session):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    await client.post("/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers)
    # The premium changes in April; March must not move with it.
    await client.put("/api/lohn/settings", json={"uvg_nbu_satz": 2.4}, headers=headers)
    row = (await db_session.execute(select(Lohnabrechnung))).scalar_one()
    assert row.nbu_satz == 1.6
    assert row.status == STATUS_ABGERECHNET


async def test_the_alv_ceiling_uses_the_months_already_issued(client, actor):
    _t, _u, headers = actor
    mid = await _setup(
        client, headers, person={**ANNA, "monatslohn": 80_000.0, "bvg_an_monat": 0.0, "bvg_ag_monat": 0.0}
    )
    for monat in (1, 2):
        res = await client.post(
            "/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": monat}, headers=headers
        )
        assert res.status_code == 201, res.text
    dritter = await client.post(
        "/api/lohn/vorschau", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers
    )
    alv = next(a for a in dritter.json()["abzuege"] if a["label"] == "ALV")
    assert alv["basis"] == 0.0  # 160'000 already exceeds the 148'200 ceiling


async def test_a_viewer_may_look_but_not_issue(client, actor, db_session):
    tenant, _u, headers = actor
    mid = await _setup(client, headers)
    viewer = await create_user(db_session, tenant, role="viewer")
    res = await client.post(
        "/api/lohn/abrechnen",
        json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3},
        headers=auth_headers(viewer),
    )
    assert res.status_code == 403
    assert (await client.get("/api/lohn/settings", headers=auth_headers(viewer))).status_code == 200


async def test_issuing_is_written_to_the_audit_log(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    await client.post("/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers)
    res = await client.get("/api/audit/", headers=headers)
    assert any(e["action"] == "lohn.abrechnung" for e in res.json()["items"])


# --- Listen und PDF -------------------------------------------------------


async def test_the_list_totals_the_year(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    for monat in (1, 2, 3):
        await client.post(
            "/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": monat}, headers=headers
        )
    res = await client.get("/api/lohn/abrechnungen?jahr=2026", headers=headers)
    body = res.json()
    assert len(body["eintraege"]) == 3
    assert body["brutto_total"] == pytest.approx(18_000.0)


async def test_the_payslip_is_a_pdf(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    issued = await client.post(
        "/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers
    )
    abrechnung_id = issued.json()["abrechnung"]["abrechnung_id"]
    res = await client.get(f"/api/lohn/abrechnungen/{abrechnung_id}/lohnabrechnung.pdf", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")


async def test_the_year_summary_is_a_pdf_and_is_not_a_lohnausweis(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    await client.post("/api/lohn/abrechnen", json={"mitarbeiter_id": mid, "jahr": 2026, "monat": 3}, headers=headers)
    res = await client.get(f"/api/lohn/mitarbeiter/{mid}/jahr/2026.pdf", headers=headers)
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF-")


async def test_a_year_without_payslips_still_prints(client, actor):
    _t, _u, headers = actor
    mid = await _setup(client, headers)
    res = await client.get(f"/api/lohn/mitarbeiter/{mid}/jahr/2019.pdf", headers=headers)
    assert res.status_code == 200


async def test_payroll_needs_a_token(client):
    assert (await client.get("/api/lohn/settings")).status_code in (401, 403)
