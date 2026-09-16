"""B-74 — was jeden Monat gleich abgeht, und was diesen Monat fehlt.

B-71 hat die Erkennung gebracht, aber nur, um die Liquidität zu rechnen. Die
Frage, die einem Inhaber am Monatsende weh tut, ist eine andere: *ist die
Miete überhaupt rausgegangen?* Das fällt sonst erst beim Abschluss auf — oder
wenn der Vermieter anruft.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.dauerbuchungen import (
    KULANZ_TAGE,
    STATUS_BEZAHLT,
    STATUS_FEHLT,
    STATUS_OFFEN,
    erkennen,
    fehlende,
    passende,
    summe_offen,
)
from tests.factories import auth_headers, create_booking, create_tenant, create_user

HEUTE = date(2026, 6, 20)


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


def _swiss(d: date) -> str:
    return d.strftime("%d.%m.%Y")


async def _monthly(db, tenant, *, label: str, betrag: float, monate, tag: int = 5, konto: str = "6000"):
    for m in monate:
        await create_booking(
            db,
            tenant,
            datum=_swiss(date(2026, m, tag)),
            beschreibung=f"{label} {m}/2026",
            kt_soll=konto,
            kt_haben="1020",
            betrag=betrag,
        )


# --- Status im laufenden Monat ----------------------------------------------


async def test_a_payment_already_made_this_month_is_settled(db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Miete Büro", betrag=1800.0, monate=(3, 4, 5, 6))

    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert len(entries) == 1
    assert entries[0].status == STATUS_BEZAHLT
    assert entries[0].tage_ueberfaellig == 0
    assert fehlende(entries) == []


async def test_a_payment_past_its_usual_day_is_missing(db_session, actor):
    """The 5th was fifteen days ago and nothing left the account."""
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Cembra Leasing", betrag=770.6, monate=(3, 4, 5))

    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert entries[0].status == STATUS_FEHLT
    assert entries[0].faellig_am == date(2026, 6, 5)
    assert entries[0].tage_ueberfaellig == 15
    assert [e.label for e in fehlende(entries)] == [entries[0].label]


async def test_a_payment_whose_day_has_not_come_is_not_missing(db_session, actor):
    """Not yet due is not the same as not paid — say so rather than cry wolf."""
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Versicherung", betrag=200.0, monate=(3, 4, 5), tag=28)

    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert entries[0].status == STATUS_OFFEN
    assert entries[0].faellig_am == date(2026, 6, 28)
    assert fehlende(entries) == []


async def test_a_direct_debit_a_day_or_two_late_is_still_only_open(db_session, actor):
    """A standing order slides around a weekend; that is not a missed payment."""
    tenant, _user, _headers = actor
    tag = HEUTE.day - KULANZ_TAGE  # exactly at the edge of the grace period
    await _monthly(db_session, tenant, label="Internet", betrag=79.0, monate=(3, 4, 5), tag=tag)

    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert entries[0].status == STATUS_OFFEN


async def test_the_usual_day_is_the_median_not_the_last_one(db_session, actor):
    tenant, _user, _headers = actor
    for m, tag in ((3, 4), (4, 5), (5, 25)):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, m, tag)),
            beschreibung="Miete",
            kt_soll="6000",
            kt_haben="1020",
            betrag=1000.0,
        )
    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert entries[0].tag == 5


async def test_the_thirty_first_survives_february():
    from app.services.dauerbuchungen import _tag_im_monat

    assert _tag_im_monat(2026, 2, 31) == date(2026, 2, 28)
    assert _tag_im_monat(2026, 4, 31) == date(2026, 4, 30)
    assert _tag_im_monat(2026, 12, 31) == date(2026, 12, 31)


# --- Was nicht als Dauerbuchung zählt ---------------------------------------


async def test_two_months_is_not_a_pattern(db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Leasing", betrag=770.6, monate=(4, 5))
    assert erkennen(await _bookings(db_session, tenant), HEUTE) == []


async def test_an_amount_that_swings_is_not_a_standing_order(db_session, actor):
    tenant, _user, _headers = actor
    for m, betrag in ((3, 120.0), (4, 480.0), (5, 95.0)):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, m, 7)),
            beschreibung="Einkauf Material",
            kt_soll="4000",
            kt_haben="1020",
            betrag=betrag,
        )
    assert erkennen(await _bookings(db_session, tenant), HEUTE) == []


async def test_money_coming_in_every_month_is_a_customer(db_session, actor):
    tenant, _user, _headers = actor
    for m in (3, 4, 5):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, m, 2)),
            beschreibung="Abo Kunde Meier",
            kt_soll="1020",
            kt_haben="3000",
            betrag=500.0,
        )
    assert erkennen(await _bookings(db_session, tenant), HEUTE) == []


# --- Summen und Reihenfolge -------------------------------------------------


async def test_what_is_still_to_go_out_excludes_what_already_went(db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Miete", betrag=1800.0, monate=(3, 4, 5, 6))  # bezahlt
    await _monthly(db_session, tenant, label="Leasing", betrag=770.6, monate=(3, 4, 5))  # fehlt
    await _monthly(db_session, tenant, label="Police", betrag=200.0, monate=(3, 4, 5), tag=28)  # offen

    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert summe_offen(entries) == 970.6


async def test_the_missing_ones_come_first_and_the_expensive_ones_above(db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Miete", betrag=1800.0, monate=(3, 4, 5, 6))
    await _monthly(db_session, tenant, label="Leasing", betrag=770.6, monate=(3, 4, 5))
    await _monthly(db_session, tenant, label="Telefon", betrag=89.0, monate=(3, 4, 5))

    statuses = [e.status for e in erkennen(await _bookings(db_session, tenant), HEUTE)]
    assert statuses[0] == STATUS_FEHLT
    assert statuses[-1] == STATUS_BEZAHLT
    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert entries[0].betrag > entries[1].betrag  # both missing, dearest first


# --- Die Zuordnung einer Bankzeile ------------------------------------------


async def test_a_bank_line_is_matched_to_the_standing_order_it_looks_like(db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Cembra Leasing", betrag=770.6, monate=(3, 4, 5))

    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    hit = passende(entries, betrag=-770.6, tag=date(2026, 6, 5))
    assert hit is not None
    assert hit.konto == "6000"


async def test_an_amount_nothing_looks_like_is_no_match(db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Cembra Leasing", betrag=770.6, monate=(3, 4, 5))
    assert passende(erkennen(await _bookings(db_session, tenant), HEUTE), betrag=-42.0) is None


async def test_two_standing_orders_of_the_same_size_are_not_guessed_between(db_session, actor):
    """Ambiguous has to stay ambiguous: this answer becomes a booking."""
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Leasing A", betrag=500.0, monate=(3, 4, 5))
    await _monthly(db_session, tenant, label="Leasing B", betrag=500.0, monate=(3, 4, 5))

    assert passende(erkennen(await _bookings(db_session, tenant), HEUTE), betrag=-500.0) is None


async def test_the_same_amount_in_a_different_month_is_not_this_months_payment(db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Miete", betrag=1800.0, monate=(3, 4, 5), tag=1)

    entries = erkennen(await _bookings(db_session, tenant), HEUTE)
    assert passende(entries, betrag=-1800.0, tag=date(2026, 6, 2)) is not None
    assert passende(entries, betrag=-1800.0, tag=date(2026, 6, 25)) is None


# --- Die API ----------------------------------------------------------------


async def test_the_endpoint_answers_with_the_declared_shape(client, db_session, actor):
    tenant, _user, headers = actor
    await create_booking(db_session, tenant, kt_soll="6000", kt_haben="1020", betrag=100.0)

    body = (await client.get("/api/dauerbuchungen/", headers=headers)).json()
    assert set(body) == {"stichtag", "monat", "eintraege", "fehlen", "offen_total", "monatstotal"}


async def test_another_tenant_sees_none_of_it(client, db_session, actor):
    tenant, _user, _headers = actor
    await _monthly(db_session, tenant, label="Miete", betrag=1800.0, monate=(3, 4, 5))

    other = await create_tenant(db_session, name="Fremd AG")
    other_user = await create_user(db_session, other, role="owner")
    body = (await client.get("/api/dauerbuchungen/", headers=auth_headers(other_user))).json()
    assert body["eintraege"] == []


async def test_signing_out_closes_the_door(client):
    assert (await client.get("/api/dauerbuchungen/")).status_code == 401


async def _bookings(db, tenant):
    from sqlalchemy import select

    from app.models.booking import Booking

    rows = await db.execute(select(Booking).where(Booking.tenant_id == tenant.id))
    return list(rows.scalars().all())
