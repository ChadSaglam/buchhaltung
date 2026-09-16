"""B-71 — 90-Tage-Liquidität und Steuerrückstellung.

Two numbers the bookkeeping never produced: how much money is expected to be
there over the next quarter, and how much of this year's profit belongs to the
tax office rather than to the owner.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.company_profile import CompanyProfile
from app.models.document import DIRECTION_AUSGANG, DIRECTION_EINGANG, STATUS_BEZAHLT, STATUS_OFFEN, Document
from app.services.liquiditaet import (
    GEWINNSTEUER_MAX,
    GEWINNSTEUER_MIN,
    LiquiditaetService,
)
from tests.factories import auth_headers, create_booking, create_tenant, create_user

HEUTE = date(2026, 6, 15)


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="owner")
    return tenant, user, auth_headers(user)


def _swiss(d: date) -> str:
    return d.strftime("%d.%m.%Y")


async def _document(
    db,
    tenant,
    *,
    amount: float,
    direction: str = DIRECTION_EINGANG,
    due: date | None = None,
    status: str = STATUS_OFFEN,
    vendor: str = "Lieferant AG",
) -> Document:
    doc = Document(
        tenant_id=tenant.id,
        status=status,
        direction=direction,
        file_key=f"receipts/{tenant.id}/x.pdf",
        filename="x.pdf",
        vendor=vendor,
        amount=amount,
        due_date=due,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# --- Kontostand -------------------------------------------------------------


async def test_the_balance_is_what_landed_on_bank_and_cash(db_session, actor):
    tenant, _user, _headers = actor
    await create_booking(db_session, tenant, kt_soll="1020", kt_haben="3000", betrag=5000.0)
    await create_booking(db_session, tenant, kt_soll="6500", kt_haben="1020", betrag=1200.0)
    await create_booking(db_session, tenant, kt_soll="1000", kt_haben="1020", betrag=300.0)  # Bank → Kasse

    service = LiquiditaetService(db_session, _user)
    bookings = await service._bookings()
    assert service.kontostand(bookings) == 3800.0


async def test_a_booking_that_never_touches_the_bank_moves_nothing(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(db_session, tenant, kt_soll="1100", kt_haben="3000", betrag=9000.0)

    service = LiquiditaetService(db_session, user)
    assert service.kontostand(await service._bookings()) == 0.0


async def test_securities_are_not_the_bank_account(db_session, actor):
    """1060 is money, but not money you can pay a supplier with today."""
    tenant, user, _headers = actor
    await create_booking(db_session, tenant, kt_soll="1060", kt_haben="3000", betrag=50_000.0)

    service = LiquiditaetService(db_session, user)
    assert service.kontostand(await service._bookings()) == 0.0


# --- Dauerbuchungen ---------------------------------------------------------


async def test_a_monthly_amount_is_recognised_without_being_typed(db_session, actor):
    tenant, user, _headers = actor
    for month in (3, 4, 5):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, month, 1)),
            beschreibung=f"Miete Büro {month}/2026",
            kt_soll="6000",
            kt_haben="1020",
            betrag=1800.0,
        )

    service = LiquiditaetService(db_session, user)
    dauer = service.dauerbuchungen(await service._bookings(), HEUTE)
    assert len(dauer) == 1
    assert dauer[0].betrag == 1800.0
    assert dauer[0].monate == 3
    assert dauer[0].konto == "6000"


async def test_two_months_is_not_a_pattern(db_session, actor):
    tenant, user, _headers = actor
    for month in (4, 5):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, month, 1)),
            beschreibung="Leasing Fahrzeug",
            kt_soll="6200",
            kt_haben="1020",
            betrag=770.6,
        )

    service = LiquiditaetService(db_session, user)
    assert service.dauerbuchungen(await service._bookings(), HEUTE) == []


async def test_an_amount_that_swings_is_not_a_standing_order(db_session, actor):
    """Groceries every month are not a subscription."""
    tenant, user, _headers = actor
    for month, betrag in ((3, 120.0), (4, 480.0), (5, 95.0)):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, month, 7)),
            beschreibung="Einkauf Material",
            kt_soll="4000",
            kt_haben="1020",
            betrag=betrag,
        )

    service = LiquiditaetService(db_session, user)
    assert service.dauerbuchungen(await service._bookings(), HEUTE) == []


async def test_income_every_month_is_a_customer_not_a_standing_cost(db_session, actor):
    tenant, user, _headers = actor
    for month in (3, 4, 5):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, month, 2)),
            beschreibung="Abo Kunde Meier",
            kt_soll="1020",
            kt_haben="3000",
            betrag=500.0,
        )

    service = LiquiditaetService(db_session, user)
    assert service.dauerbuchungen(await service._bookings(), HEUTE) == []


async def test_a_standing_cost_is_projected_over_the_window(db_session, actor):
    tenant, user, _headers = actor
    for month in (3, 4, 5):
        await create_booking(
            db_session,
            tenant,
            datum=_swiss(date(2026, month, 1)),
            beschreibung="Versicherung",
            kt_soll="6300",
            kt_haben="1020",
            betrag=200.0,
        )

    service = LiquiditaetService(db_session, user)
    dauer = service.dauerbuchungen(await service._bookings(), HEUTE)
    positionen = service.dauer_positionen(dauer, HEUTE, HEUTE + timedelta(days=90))
    # 15.06. + 90 days is 13.09., so the September instalment falls outside.
    assert [p.datum for p in positionen] == [date(2026, 7, 15), date(2026, 8, 15)]
    assert all(p.betrag == -200.0 for p in positionen)


# --- Offene Posten ----------------------------------------------------------


async def test_our_invoice_is_money_in_and_a_supplier_bill_is_money_out(db_session, actor):
    tenant, user, _headers = actor
    await _document(db_session, tenant, amount=1000.0, direction=DIRECTION_AUSGANG, due=HEUTE + timedelta(days=10))
    await _document(db_session, tenant, amount=400.0, direction=DIRECTION_EINGANG, due=HEUTE + timedelta(days=20))

    service = LiquiditaetService(db_session, user)
    positionen = service.dokument_positionen(await service._open_documents(), HEUTE, HEUTE + timedelta(days=90), 30)
    assert sorted(p.betrag for p in positionen) == [-400.0, 1000.0]


async def test_an_overdue_invoice_counts_from_today_not_from_the_past(db_session, actor):
    tenant, user, _headers = actor
    await _document(db_session, tenant, amount=900.0, direction=DIRECTION_AUSGANG, due=HEUTE - timedelta(days=45))

    service = LiquiditaetService(db_session, user)
    position = service.dokument_positionen(await service._open_documents(), HEUTE, HEUTE + timedelta(days=90), 30)[0]
    assert position.datum == HEUTE
    assert position.ueberfaellig is True


async def test_a_paid_invoice_is_not_expected_money(db_session, actor):
    tenant, user, _headers = actor
    await _document(db_session, tenant, amount=900.0, status=STATUS_BEZAHLT, due=HEUTE + timedelta(days=5))

    service = LiquiditaetService(db_session, user)
    assert await service._open_documents() == []


async def test_an_invoice_due_after_the_window_stays_out(db_session, actor):
    tenant, user, _headers = actor
    await _document(db_session, tenant, amount=900.0, direction=DIRECTION_AUSGANG, due=HEUTE + timedelta(days=200))

    service = LiquiditaetService(db_session, user)
    assert service.dokument_positionen(await service._open_documents(), HEUTE, HEUTE + timedelta(days=90), 30) == []


# --- Steuer -----------------------------------------------------------------


async def test_without_a_rate_nothing_is_estimated(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 3, 1)), kt_soll="1020", kt_haben="3000", betrag=80_000.0
    )

    service = LiquiditaetService(db_session, user)
    steuer = service.steuer(await service._bookings(), HEUTE, None)
    assert steuer.gewinn == 80_000.0
    assert steuer.satz is None
    assert steuer.rueckstellung_soll is None
    assert "Treuhänder" in steuer.hinweis


async def test_the_quoted_range_is_the_one_estv_publishes():
    """A number nobody can source is a number nobody should act on."""
    assert GEWINNSTEUER_MIN < GEWINNSTEUER_MAX
    assert 11.0 < GEWINNSTEUER_MIN < 12.0  # Luzern 2026
    assert 20.0 < GEWINNSTEUER_MAX < 21.0  # Bern 2026


async def test_the_provision_is_profit_times_the_rate_the_owner_entered(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 2, 1)), kt_soll="1020", kt_haben="3000", betrag=100_000.0
    )
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 3, 1)), kt_soll="6500", kt_haben="1020", betrag=40_000.0
    )

    service = LiquiditaetService(db_session, user)
    steuer = service.steuer(await service._bookings(), HEUTE, 14.43)
    assert steuer.ertrag == 100_000.0
    assert steuer.aufwand == 40_000.0
    assert steuer.gewinn == 60_000.0
    assert steuer.rueckstellung_soll == 8658.0
    assert steuer.offen == 8658.0
    # June is in Q2, so the rest of Q2 plus Q3 and Q4 are left to put it aside.
    assert steuer.pro_quartal == 2886.0


async def test_what_is_already_provisioned_is_subtracted(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 2, 1)), kt_soll="1020", kt_haben="3000", betrag=100_000.0
    )
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 4, 1)), kt_soll="8900", kt_haben="2201", betrag=10_000.0
    )

    service = LiquiditaetService(db_session, user)
    steuer = service.steuer(await service._bookings(), HEUTE, 14.43)
    assert steuer.schon_zurueckgestellt == 10_000.0
    # The provision booking itself must not shrink the profit it is computed on.
    assert steuer.gewinn == 100_000.0
    assert steuer.rueckstellung_soll == 14_430.0
    assert steuer.offen == 4430.0


async def test_a_loss_owes_nothing(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 2, 1)), kt_soll="1020", kt_haben="3000", betrag=10_000.0
    )
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 3, 1)), kt_soll="6500", kt_haben="1020", betrag=25_000.0
    )

    service = LiquiditaetService(db_session, user)
    steuer = service.steuer(await service._bookings(), HEUTE, 14.43)
    assert steuer.gewinn == -15_000.0
    assert steuer.offen == 0.0


async def test_last_years_profit_is_not_this_years_tax(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2025, 11, 1)), kt_soll="1020", kt_haben="3000", betrag=90_000.0
    )

    service = LiquiditaetService(db_session, user)
    steuer = service.steuer(await service._bookings(), HEUTE, 14.43)
    assert steuer.jahr == 2026
    assert steuer.gewinn == 0.0


async def test_an_over_provision_never_reads_as_a_refund(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 2, 1)), kt_soll="1020", kt_haben="3000", betrag=10_000.0
    )
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 4, 1)), kt_soll="8900", kt_haben="2201", betrag=9_000.0
    )

    service = LiquiditaetService(db_session, user)
    steuer = service.steuer(await service._bookings(), HEUTE, 14.43)
    assert steuer.offen == 0.0


# --- Der ganze Report -------------------------------------------------------


async def test_the_report_adds_the_balance_the_inflows_and_the_outflows(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 1, 5)), kt_soll="1020", kt_haben="3000", betrag=20_000.0
    )
    await _document(db_session, tenant, amount=5_000.0, direction=DIRECTION_AUSGANG, due=HEUTE + timedelta(days=10))
    await _document(db_session, tenant, amount=3_000.0, direction=DIRECTION_EINGANG, due=HEUTE + timedelta(days=20))

    report = await LiquiditaetService(db_session, user).report(heute=HEUTE)
    assert report.stand_heute == 20_000.0
    assert report.eingang == 5_000.0
    assert report.ausgang == 3_000.0
    assert report.prognose == 22_000.0
    assert report.bis == HEUTE + timedelta(days=90)


async def test_the_report_names_the_day_the_money_runs_out(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 1, 5)), kt_soll="1020", kt_haben="3000", betrag=1_000.0
    )
    await _document(db_session, tenant, amount=4_000.0, direction=DIRECTION_EINGANG, due=HEUTE + timedelta(days=5))
    await _document(db_session, tenant, amount=9_000.0, direction=DIRECTION_AUSGANG, due=HEUTE + timedelta(days=40))

    report = await LiquiditaetService(db_session, user).report(heute=HEUTE)
    # The bill lands before the customer pays, so the trough is in between.
    assert report.tiefster_stand == -3_000.0
    assert report.tiefster_am == HEUTE + timedelta(days=5)
    assert report.prognose == 6_000.0  # ends fine; the point is that it dips first
    assert any("unter null" in w for w in report.warnungen)


async def test_the_report_says_the_balance_is_only_what_it_booked(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(db_session, tenant, kt_soll="1020", kt_haben="3000", betrag=100.0)

    report = await LiquiditaetService(db_session, user).report(heute=HEUTE)
    assert any("Eröffnungsbilanz" in w for w in report.warnungen)


async def test_an_empty_tenant_gets_zeroes_and_an_explanation(db_session, actor):
    _tenant, user, _headers = actor
    report = await LiquiditaetService(db_session, user).report(heute=HEUTE)
    assert report.stand_heute == 0.0
    assert report.prognose == 0.0
    assert report.positionen == []
    assert any("Kasse oder Bank" in w for w in report.warnungen)


async def test_the_months_add_up_to_the_totals(db_session, actor):
    tenant, user, _headers = actor
    await create_booking(
        db_session, tenant, datum=_swiss(date(2026, 1, 5)), kt_soll="1020", kt_haben="3000", betrag=10_000.0
    )
    for offset in (5, 40, 75):
        await _document(
            db_session, tenant, amount=1_000.0, direction=DIRECTION_AUSGANG, due=HEUTE + timedelta(days=offset)
        )

    report = await LiquiditaetService(db_session, user).report(heute=HEUTE)
    assert round(sum(m.eingang for m in report.monate), 2) == report.eingang
    assert round(sum(m.ausgang for m in report.monate), 2) == report.ausgang
    assert report.monate[-1].saldo_ende == report.prognose


# --- Die API ----------------------------------------------------------------


async def test_the_endpoint_answers_with_the_declared_shape(client, db_session, actor):
    tenant, _user, headers = actor
    await create_booking(db_session, tenant, kt_soll="1020", kt_haben="3000", betrag=1_000.0)

    response = await client.get("/api/liquiditaet/", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "stichtag",
        "bis",
        "stand_heute",
        "eingang",
        "ausgang",
        "prognose",
        "tiefster_stand",
        "tiefster_am",
        "positionen",
        "dauerbuchungen",
        "monate",
        "warnungen",
        "steuer",
    }
    assert body["steuer"]["satz"] is None


async def test_the_endpoint_uses_the_rate_from_the_company_profile(client, db_session, actor):
    tenant, _user, headers = actor
    db_session.add(CompanyProfile(tenant_id=tenant.id, name="Muster GmbH", gewinnsteuer_satz=14.43))
    await create_booking(
        db_session, tenant, datum=_swiss(date.today()), kt_soll="1020", kt_haben="3000", betrag=1_000.0
    )
    await db_session.commit()

    body = (await client.get("/api/liquiditaet/", headers=headers)).json()
    assert body["steuer"]["satz"] == 14.43
    assert body["steuer"]["rueckstellung_soll"] == 144.3


async def test_another_tenant_sees_none_of_it(client, db_session, actor):
    tenant, _user, _headers = actor
    await create_booking(db_session, tenant, kt_soll="1020", kt_haben="3000", betrag=50_000.0)

    other = await create_tenant(db_session, name="Fremd AG")
    other_user = await create_user(db_session, other, role="owner")
    body = (await client.get("/api/liquiditaet/", headers=auth_headers(other_user))).json()
    assert body["stand_heute"] == 0.0


async def test_signing_out_closes_the_door(client):
    assert (await client.get("/api/liquiditaet/")).status_code == 401
