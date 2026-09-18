"""Amount memory (Betrag-Gedächtnis) — bank lines without a counterparty.

A UBS PDF prints "E-BANKING-AUFTRAG 770.60" and nothing else; the tenant booked
770.60 twelve times to 6260 "Cembra Money, Leasing". The amount is the key.
"""

from __future__ import annotations

import pytest

from app.services.classifier import (
    AMOUNT_MAX_CONFIDENCE,
    KEIN_VORSCHLAG,
    RULE_CONFIDENCE,
    ClassificationResult,
    amount_candidate,
)
from tests.factories import create_booking, create_tenant, create_training_row
from tests.test_classifier import FakeModel, _clf


def _rows(n: int, soll="6260", haben="1020", desc="Cembra Money, Leasing", code="", pct=""):
    return [(desc, soll, haben, code, pct) for _ in range(n)]


# ── pure scoring ─────────────────────────────────────────────────────────────


def test_needs_two_agreeing_bookings():
    assert amount_candidate([], 770.60) is None
    assert amount_candidate(_rows(1), 770.60) is None
    assert amount_candidate(_rows(1) + _rows(1, soll="5820", desc="Bezug"), 300.0) is None


def test_consistent_history_is_confident_and_carries_the_description():
    r = amount_candidate(_rows(12), 770.60)
    assert isinstance(r, ClassificationResult)
    assert (r.kt_soll, r.kt_haben, r.source) == ("6260", "1020", "Betrag")
    assert r.confidence == pytest.approx(AMOUNT_MAX_CONFIDENCE)
    assert r.beschreibung_vorschlag == "Cembra Money, Leasing"


def test_two_of_two_is_above_rule_default_but_below_a_keyword_rule():
    r = amount_candidate(_rows(2), 87.55)
    assert r is not None
    assert 0.35 < r.confidence < RULE_CONFIDENCE


def test_disagreement_lowers_confidence_and_below_60_percent_gives_up():
    # 11 × Swiss Life 5720, 6 × Bezug 5820 (real 2024 history for 300.00): 61 % → unsure, not silent
    r = amount_candidate(_rows(11, soll="5720", desc="Swiss Life") + _rows(6, soll="5820", desc="Bezug"), 300.0)
    assert r is not None
    assert r.kt_soll == "5720"
    assert 0.5 < r.confidence < 0.6
    # 50/50 → nothing
    assert amount_candidate(_rows(3, soll="5720") + _rows(3, soll="5820"), 300.0) is None


def test_vat_and_description_come_from_the_agreeing_rows_only():
    rows = _rows(3, soll="4000", desc="Iso Center, Mat.", code="M81", pct="8.10") + _rows(1, soll="6500", desc="x")
    r = amount_candidate(rows, 804.90)
    assert r is not None
    assert (r.mwst_code, r.mwst_pct, r.beschreibung_vorschlag) == ("M81", "8.10", "Iso Center, Mat.")
    assert r.mwst_amount == pytest.approx(60.31)


# ── inside the classifier chain ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_amount_memory_reads_training_rows_and_bookings(db_session):
    tenant = await create_tenant(db_session)
    for _ in range(2):
        await create_training_row(db_session, tenant, "Cembra Money, Leasing", "6260", betrag=770.60)
    await create_booking(db_session, tenant, beschreibung="Cembra Money, Leasing", betrag=770.6, kt_soll="6260")
    await create_training_row(db_session, tenant, "unrelated", "9999", betrag=770.61)
    clf = await _clf(db_session, tenant.id)

    r = await clf.classify("E-BANKING-AUFTRAG", False, 770.60)
    assert (r.source, r.kt_soll, r.beschreibung_vorschlag) == ("Betrag", "6260", "Cembra Money, Leasing")
    assert r.confidence == pytest.approx(min(AMOUNT_MAX_CONFIDENCE, 0.55 + 0.06 * 3))


@pytest.mark.asyncio
async def test_amount_memory_is_tenant_scoped(db_session):
    tenant_a = await create_tenant(db_session)
    tenant_b = await create_tenant(db_session)
    for _ in range(5):
        await create_training_row(db_session, tenant_b, "Geheim", "1234", betrag=42.0)
    clf = await _clf(db_session, tenant_a.id)

    r = await clf.classify("E-BANKING-AUFTRAG", False, 42.0)
    # B-92: an E-BANKING-AUFTRAG names no counterparty, and this tenant has no
    # memory of its own — so the answer is blank, not 6500.
    assert r.source == KEIN_VORSCHLAG
    assert r.kt_soll != "1234"


@pytest.mark.asyncio
async def test_keyword_rule_beats_hesitant_model_but_not_a_sure_one(db_session):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id, FakeModel(["3000"], [0.48]))
    r = await clf.classify("SALDO DIENSTLEISTUNGSPREISABSCHLUSS", False, 4.0)
    assert (r.source, r.kt_soll) == ("Regeln", "6900")

    tenant2 = await create_tenant(db_session)
    clf2 = await _clf(db_session, tenant2.id, FakeModel(["6940"], [0.9]))
    r2 = await clf2.classify("SALDO DIENSTLEISTUNGSPREISABSCHLUSS", False, 4.0)
    assert (r2.source, r2.kt_soll) == ("ML", "6940")


@pytest.mark.asyncio
async def test_weak_amount_hit_only_lends_its_description(db_session):
    tenant = await create_tenant(db_session)
    for _ in range(2):
        await create_training_row(db_session, tenant, "Agrola, TS", "6210", betrag=153.05)
    clf = await _clf(db_session, tenant.id)

    r = await clf.classify("ZAHLUNG DEBITKARTE AGROLA", False, 153.05)
    assert r.source == "Regeln"  # keyword rule 0.72 > 2/2 amount hit 0.67
    assert r.kt_soll == "6210"
    assert r.beschreibung_vorschlag == "Agrola, TS"


@pytest.mark.asyncio
async def test_description_is_dropped_when_another_tier_picks_a_different_account(db_session):
    tenant = await create_tenant(db_session)
    for _ in range(3):
        await create_training_row(db_session, tenant, "Swiss Life", "5720", betrag=300.0)
    clf = await _clf(db_session, tenant.id, FakeModel(["5820"], [0.92]))

    r = await clf.classify("BEZUG UBS BANCOMAT", False, 300.0)
    assert (r.source, r.kt_soll) == ("ML", "5820")
    assert r.beschreibung_vorschlag == ""


@pytest.mark.asyncio
async def test_credit_keeps_revenue_default_but_gets_the_customer_name(db_session):
    tenant = await create_tenant(db_session)
    for _ in range(2):
        await create_training_row(
            db_session,
            tenant,
            "Ammann+Schmit Ag, Ertrag",
            "1020",
            kt_haben="3000",
            mwst_code="V81",
            mwst_pct="-8.10",
            betrag=5945.50,
        )
    clf = await _clf(db_session, tenant.id)

    r = await clf.classify("GUTSCHRIFT", True, 5945.50)
    assert (r.kt_soll, r.kt_haben, r.mwst_code) == ("1020", "3000", "V81")
    assert r.confidence == 1.0  # agreeing history must not downgrade a sure line
    assert r.beschreibung_vorschlag == "Ammann+Schmit Ag, Ertrag"


@pytest.mark.asyncio
async def test_credit_follows_history_when_it_points_elsewhere(db_session):
    tenant = await create_tenant(db_session)
    for _ in range(4):
        await create_training_row(db_session, tenant, "Kunde X, Debitor", "1100", kt_haben="1020", betrag=999.0)
    clf = await _clf(db_session, tenant.id)
    r = await clf.classify("GUTSCHRIFT", True, 999.0)
    assert (r.source, r.kt_soll, r.kt_haben) == ("Betrag", "1100", "1020")


@pytest.mark.asyncio
async def test_zero_or_missing_amount_is_ignored(db_session):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)
    assert await clf._amount_history(0) == []
    assert await clf._amount_history(float("nan")) == []
    assert await clf._amount_history(float("inf")) == []
