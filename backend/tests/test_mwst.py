"""MWST-Abrechnung (B-67): Formular-200-Ziffern, Saldosteuersatz, Plausibilität, Isolation."""

from __future__ import annotations

from datetime import date

import pytest

from app.models.booking import Booking
from app.services.mwst import (
    METHODE_SALDO,
    SIDE_INVEST,
    SIDE_KEINE,
    SIDE_MATERIAL,
    SIDE_UMSATZ,
    MwstService,
    booking_rate,
    booking_side,
    code_side,
    copy_block,
    default_quarter,
    is_revenue_reduction,
    quarter_bounds,
    quarter_key,
    quarter_label,
    render_text,
    side_disagrees_with_accounts,
    tax_of,
)
from tests.factories import auth_headers, create_tenant, create_user

Q2 = "2026-Q2"


@pytest.fixture
async def actor(db_session):
    tenant = await create_tenant(db_session, name="Muster GmbH")
    user = await create_user(db_session, tenant, role="editor")
    return tenant, user, auth_headers(user)


async def add(
    db,
    tenant,
    *,
    datum="15.05.2026",
    betrag=1081.0,
    soll="1020",
    haben="3000",
    code="V81",
    pct="8.10",
    mwst=81.0,
) -> Booking:
    booking = Booking(
        tenant_id=tenant.id,
        datum=datum,
        beschreibung="Beleg",
        betrag=betrag,
        kt_soll=soll,
        kt_haben=haben,
        mwst_code=code,
        mwst_pct=pct,
        mwst_amount=mwst,
        source="test",
    )
    db.add(booking)
    await db.flush()
    return booking


# ── pure helpers ─────────────────────────────────────────────────────────────


def test_quarter_bounds_labels_and_keys():
    assert quarter_bounds("2026-Q1") == (date(2026, 1, 1), date(2026, 3, 31))
    assert quarter_bounds("2026-Q2") == (date(2026, 4, 1), date(2026, 6, 30))
    assert quarter_bounds("2026-q4") == (date(2026, 10, 1), date(2026, 12, 31))
    assert quarter_key(date(2026, 5, 15)) == "2026-Q2"
    assert quarter_key(None) is None
    assert quarter_label("2026-Q2") == "01.04.2026 – 30.06.2026"
    assert default_quarter([date(2026, 5, 1)]) == "2026-Q2"
    assert default_quarter([], today=date(2026, 9, 15)) == "2026-Q3"


def test_a_bad_quarter_is_a_clear_400():
    for bad in ("2026-Q5", "Q2", "2026"):
        with pytest.raises(Exception) as exc:
            quarter_bounds(bad)
        assert exc.value.status_code == 400
        assert "JJJJ-Qn" in str(exc.value.detail)


def test_banana_code_prefixes_pick_the_side():
    assert code_side("V81") == SIDE_UMSATZ
    assert code_side("M81") == SIDE_MATERIAL
    assert code_side("I26") == SIDE_INVEST
    assert code_side("") == SIDE_KEINE
    assert code_side("X99") == SIDE_KEINE


def test_without_a_code_the_accounts_decide():
    assert booking_side(Booking(kt_soll="1020", kt_haben="3000", mwst_code="")) == SIDE_UMSATZ
    assert booking_side(Booking(kt_soll="4000", kt_haben="1020", mwst_code="")) == SIDE_MATERIAL
    assert booking_side(Booking(kt_soll="6500", kt_haben="1020", mwst_code="")) == SIDE_INVEST
    assert booking_side(Booking(kt_soll="1500", kt_haben="1020", mwst_code="")) == SIDE_INVEST
    assert booking_side(Booking(kt_soll="1020", kt_haben="2000", mwst_code="")) == SIDE_KEINE
    # The code wins when both speak.
    assert booking_side(Booking(kt_soll="4000", kt_haben="1020", mwst_code="V81")) == SIDE_UMSATZ


def test_a_code_on_the_wrong_side_is_flagged():
    assert side_disagrees_with_accounts(Booking(kt_soll="4000", kt_haben="1020", mwst_code="V81"))
    assert side_disagrees_with_accounts(Booking(kt_soll="1020", kt_haben="3000", mwst_code="M81"))
    assert not side_disagrees_with_accounts(Booking(kt_soll="1020", kt_haben="3000", mwst_code="V81"))
    assert not side_disagrees_with_accounts(Booking(kt_soll="4000", kt_haben="1020", mwst_code="M81"))
    assert not side_disagrees_with_accounts(Booking(kt_soll="1020", kt_haben="2000", mwst_code="V81"))


def test_tax_uses_the_stored_amount_then_the_rate():
    assert tax_of(Booking(betrag=1081.0, mwst_pct="8.10", mwst_amount=81.0)) == 81.0
    assert tax_of(Booking(betrag=1081.0, mwst_pct="8.10", mwst_amount=0.0)) == 81.0
    assert tax_of(Booking(betrag=1081.0, mwst_pct="", mwst_amount=0.0)) == 0.0
    assert booking_rate(Booking(mwst_pct="8.10")) == 8.1
    assert booking_rate(Booking(mwst_pct="")) is None
    assert booking_rate(Booking(mwst_pct="acht")) is None


def test_credit_notes_are_revenue_reductions():
    assert is_revenue_reduction(Booking(kt_soll="3000", kt_haben="1100", betrag=100.0, mwst_code="V81"))
    assert is_revenue_reduction(Booking(kt_soll="1020", kt_haben="3000", betrag=-50.0, mwst_code="V81"))
    assert not is_revenue_reduction(Booking(kt_soll="1020", kt_haben="3000", betrag=50.0, mwst_code="V81"))


# ── effektive Methode ────────────────────────────────────────────────────────


async def test_effektiv_fills_the_form_200_ziffern(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant, betrag=10810.0, mwst=810.0)  # Umsatz 8.1 %
    await add(db_session, tenant, betrag=1026.0, code="V26", pct="2.60", mwst=26.0)  # reduziert
    await add(db_session, tenant, betrag=540.0, soll="3000", haben="1100", mwst=40.0)  # Gutschrift
    await add(db_session, tenant, betrag=1081.0, soll="4000", haben="1020", code="M81", mwst=81.0)
    await add(db_session, tenant, betrag=2162.0, soll="6500", haben="1020", code="I81", mwst=162.0)

    report = await MwstService(db_session, user).report(Q2)
    values = {r.ziffer: r for r in report.ziffern}
    assert report.quartal == Q2
    assert report.zeitraum == "01.04.2026 – 30.06.2026"
    assert values["200"].umsatz == 11836.0  # 10810 + 1026
    assert values["235"].umsatz == 540.0
    assert values["289"].umsatz == 540.0
    assert values["299"].umsatz == 11296.0
    assert (values["302"].umsatz, values["302"].steuer) == (10810.0, 810.0)
    assert (values["312"].umsatz, values["312"].steuer) == (1026.0, 26.0)
    assert values["342"].steuer == 0.0
    assert values["399"].steuer == 836.0
    assert values["400"].steuer == 81.0
    assert values["405"].steuer == 162.0
    assert values["479"].steuer == 243.0
    assert values["500"].steuer == 593.0
    assert values["510"].steuer == 0.0


async def test_more_vorsteuer_than_steuer_becomes_a_guthaben(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant, betrag=1081.0, mwst=81.0)
    await add(db_session, tenant, betrag=5405.0, soll="4000", haben="1020", code="M81", mwst=405.0)

    report = await MwstService(db_session, user).report(Q2)
    values = {r.ziffer: r.steuer for r in report.ziffern}
    assert values["500"] == 0.0
    assert values["510"] == 324.0


async def test_only_the_asked_quarter_counts(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant, datum="15.05.2026", betrag=1081.0, mwst=81.0)
    await add(db_session, tenant, datum="15.08.2026", betrag=2162.0, mwst=162.0)

    service = MwstService(db_session, user)
    q2 = await service.report("2026-Q2")
    q3 = await service.report("2026-Q3")
    assert q2.value("200") == 1081.0
    assert q3.value("200") == 2162.0
    assert await service.quarters() == ["2026-Q3", "2026-Q2"]


async def test_ziffern_without_a_booking_basis_stay_zero(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant)
    report = await MwstService(db_session, user).report(Q2)
    values = {r.ziffer: r for r in report.ziffern}
    for ziffer in ("205", "220", "221", "225", "230", "280", "382", "410", "415", "420"):
        row = values[ziffer]
        assert (row.umsatz or 0.0) == 0.0
        assert (row.steuer or 0.0) == 0.0


# ── Saldosteuersatz ──────────────────────────────────────────────────────────


async def test_saldosteuersatz_is_umsatz_times_rate_without_vorsteuer(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant, betrag=10000.0, mwst=0.0, pct="8.10")
    await add(db_session, tenant, betrag=1081.0, soll="4000", haben="1020", code="M81", mwst=81.0)

    report = await MwstService(db_session, user).report(Q2, methode=METHODE_SALDO, satz=6.5)
    values = {r.ziffer: r for r in report.ziffern}
    assert report.methode == METHODE_SALDO
    assert report.satz == 6.5
    assert values["299"].umsatz == 10000.0
    assert values["322"].steuer == 650.0
    assert values["399"].steuer == 650.0
    assert values["500"].steuer == 650.0
    assert "400" not in values  # keine Vorsteuer in dieser Methode


async def test_saldo_without_a_rate_and_a_silly_rate_are_refused(db_session, actor):
    _tenant, user, _ = actor
    service = MwstService(db_session, user)
    with pytest.raises(Exception) as missing:
        await service.report(Q2, methode=METHODE_SALDO)
    assert missing.value.status_code == 400
    with pytest.raises(Exception) as silly:
        await service.report(Q2, methode=METHODE_SALDO, satz=99.0)
    assert silly.value.status_code == 400
    with pytest.raises(Exception) as unknown:
        await service.report(Q2, methode="raten")
    assert unknown.value.status_code == 400


# ── Plausibilität ────────────────────────────────────────────────────────────


async def test_plausibility_names_every_problem(db_session, actor):
    tenant, user, _ = actor
    wrong_code = await add(db_session, tenant, code="V26", pct="8.10")  # Code ≠ Satz
    wrong_side = await add(db_session, tenant, soll="4000", haben="1020", code="V81")  # V auf Aufwand
    odd_rate = await add(db_session, tenant, code="V81", pct="5.00")  # kein CH-Satz
    no_vat = await add(db_session, tenant, soll="4000", haben="1020", code="", pct="", mwst=0.0)
    no_side = await add(db_session, tenant, soll="1020", haben="2000", code="", pct="", mwst=0.0)

    report = await MwstService(db_session, user).report(Q2)
    flagged = {c.code: c for c in report.checks}
    assert wrong_code.id in flagged["mwst_unstimmig"].booking_ids
    assert wrong_side.id in flagged["code_seite_falsch"].booking_ids
    assert odd_rate.id in flagged["satz_unbekannt"].booking_ids
    assert no_vat.id in flagged["vorsteuer_fehlt"].booking_ids
    assert no_side.id in flagged["ohne_seite"].booking_ids
    assert report.blockers >= 3
    assert report.ready is False


async def test_a_clean_quarter_has_nothing_to_flag(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant)
    await add(db_session, tenant, soll="4000", haben="1020", code="M81")
    report = await MwstService(db_session, user).report(Q2)
    assert report.blockers == 0
    assert report.ready is True
    assert all(c.count == 0 for c in report.checks)


# ── Ausgabe ──────────────────────────────────────────────────────────────────


async def test_copy_block_is_tab_separated_plain_numbers(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant, betrag=10810.0, mwst=810.0)
    report = await MwstService(db_session, user).report(Q2)
    block = copy_block(report)
    assert "200\t10810.00" in block
    assert "302\t810.00" in block
    assert "'" not in block  # keine Schweizer Apostrophe im Kopierblock
    assert block.startswith("# MWST-Abrechnung 2026-Q2")


async def test_text_sheet_reads_like_the_form(db_session, actor):
    tenant, user, _ = actor
    await add(db_session, tenant, betrag=10810.0, mwst=810.0)
    sheet = render_text(await MwstService(db_session, user).report(Q2))
    assert "MWST-Abrechnung 2026-Q2" in sheet
    assert "Steuerbarer Gesamtumsatz" in sheet
    assert "10'810.00" in sheet
    assert "Entwurf aus den Buchungen" in sheet


# ── HTTP ─────────────────────────────────────────────────────────────────────


async def test_http_quarters_report_and_sheet(client, db_session, actor):
    tenant, _, headers = actor
    await add(db_session, tenant, betrag=10810.0, mwst=810.0)
    await db_session.commit()

    quarters = await client.get("/api/abschluss/quartale", headers=headers)
    assert quarters.status_code == 200
    assert quarters.json()["quartale"] == [Q2]
    assert quarters.json()["aktuell"] == Q2

    report = await client.get("/api/abschluss/mwst", headers=headers)
    assert report.status_code == 200
    body = report.json()
    assert body["quartal"] == Q2
    assert body["methode"] == "effektiv"
    assert body["zu_bezahlen"] == 810.0
    assert body["guthaben"] == 0.0
    assert any(z["ziffer"] == "299" for z in body["ziffern"])
    assert "200\t10810.00" in body["copy_block"]

    saldo = await client.get(f"/api/abschluss/mwst?quartal={Q2}&methode=saldo&satz=6.5", headers=headers)
    assert saldo.json()["satz"] == 6.5
    assert saldo.json()["zu_bezahlen"] == 702.65  # 10810 × 6.5 %

    sheet = await client.get(f"/api/abschluss/mwst.txt?quartal={Q2}", headers=headers)
    assert sheet.status_code == 200
    assert "MWST-Abrechnung" in sheet.text
    assert "attachment" in sheet.headers["content-disposition"]

    bad = await client.get("/api/abschluss/mwst?quartal=2026-Q9", headers=headers)
    assert bad.status_code == 400


async def test_another_tenant_sees_its_own_figures_only(client, db_session, actor):
    tenant, _, headers = actor
    await add(db_session, tenant, betrag=10810.0, mwst=810.0)
    other_tenant = await create_tenant(db_session)
    other = await create_user(db_session, other_tenant, role="owner")
    await db_session.commit()

    mine = await client.get(f"/api/abschluss/mwst?quartal={Q2}", headers=headers)
    theirs = await client.get(f"/api/abschluss/mwst?quartal={Q2}", headers=auth_headers(other))
    assert mine.json()["zu_bezahlen"] == 810.0
    assert theirs.json()["zu_bezahlen"] == 0.0
    assert theirs.json()["buchungen"] == 0
    assert (await client.get("/api/abschluss/mwst")).status_code == 401
    assert (await client.get("/api/abschluss/quartale")).status_code == 401
    assert (await client.get("/api/abschluss/mwst.txt")).status_code == 401
