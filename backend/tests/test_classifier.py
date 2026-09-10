"""Classifier — memory -> ML -> rules layering, VAT maths, thresholds, corrections.

Layer order in TenantClassifier.classify():
  1. credit note shortcut (is_credit)            confidence 1.0, "Regeln"
  2. exact memory hit (tenant-scoped)             confidence 1.0, "Gedächtnis"
  3. ML model if present and proba >= 0.45        confidence = proba, "ML"
  4. keyword rules, default 6500/1020 at 0.35     "Regeln"
"""

from __future__ import annotations

import pickle

import numpy as np
import pytest
from sqlalchemy import select

from app.models.accuracy_history import AccuracyHistory
from app.models.classifier_model import ClassifierModel
from app.models.correction import Correction
from app.models.memory import Memory
from app.services.classifier import (
    AUTO_RETRAIN_THRESHOLD,
    CLASSIFICATION_RULES,
    CONFIDENCE_THRESHOLD,
    DEFAULT_RULE_CONFIDENCE,
    RULE_CONFIDENCE,
    ClassificationResult,
    TenantClassifier,
    calc_mwst,
    make_memory_key,
    preprocess,
)
from app.services.review_queue import DEFAULT_THRESHOLD, ReviewQueueService
from tests.factories import (
    create_konto_default,
    create_memory,
    create_scanner_config,
    create_tenant,
    create_training_row,
    create_user,
)


class FakeModel:
    """Picklable stand-in for the sklearn pipeline: fixed classes, scripted probabilities."""

    def __init__(self, classes: list[str], proba: list[float]):
        self.classes_ = np.array(classes)
        self._proba = np.array(proba)
        self.seen: list[str] = []

    def predict_proba(self, texts):
        self.seen.extend(texts)
        return np.array([self._proba for _ in texts])


async def _clf(db_session, tenant_id: int, model: FakeModel | None = None) -> TenantClassifier:
    clf = TenantClassifier(tenant_id, db_session)
    if model is not None:
        db_session.add(ClassifierModel(tenant_id=tenant_id, model_blob=pickle.dumps(model)))
        await db_session.commit()
    return clf


# ── preprocess / memory key ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Swisscom Rechnung 2025", "swisscom rechnung"),
        ("  COOP   Filiale 123  ", "coop filiale"),
        ("Miete Januar 2025", "miete"),
        ("Zahlung 15.03.2025 Nr 4711", "zahlung .. nr"),  # digits go, punctuation stays
        ("", ""),
        (None, ""),
    ],
)
def test_preprocess_lowercases_and_strips_digits_and_months(raw, expected):
    assert preprocess(raw) == expected


# B-04: month tokens are stripped as whole words only.
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("E-Mail Swisscom 2025", "e-mail swisscom"),  # was "e-l swisscom"
        ("SEPARAT Rechnung", "separat rechnung"),  # was "arat rechnung"
        ("Julia Novak", "julia novak"),  # was "ia ak"
        ("Mailand Reise", "mailand reise"),
        ("Miete Feb. 2025", "miete"),  # abbreviation with dot
        ("Miete feb 2025", "miete"),
        ("Rechnung März 24", "rechnung"),
        ("Abo Mrz. 2025", "abo"),
        ("Sept. Abo", "abo"),
        ("Dezember-Abschluss", "-abschluss"),  # hyphen is a word boundary, like before
        ("Jan Müller AG", "müller ag"),  # a first name that is a month token still goes (unchanged)
    ],
)
def test_preprocess_strips_months_as_whole_words_only(raw, expected):
    assert preprocess(raw) == expected


def test_memory_key_no_longer_collides_on_month_substrings():
    assert make_memory_key("E-Mail Hosting") != make_memory_key("E-l Hosting")
    assert make_memory_key("Julia Novak") != make_memory_key("ia ak")


def test_memory_key_is_stable_across_dates_and_case():
    assert make_memory_key("Swisscom Rechnung März 2025") == make_memory_key("SWISSCOM Rechnung April 2024")


# ── VAT maths ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("betrag", "pct", "expected"),
    [
        (108.10, "8.10", 8.10),  # gross incl. 8.1% -> tax portion
        (100.0, "8.10", 7.49),
        (102.60, "2.60", 2.60),
        (1000.0, "8.1", 74.93),
        (108.10, "-8.10", -8.10),  # negative rate flips sign (Vorsteuer/Umsatzsteuer)
        (-108.10, "8.10", -8.10),  # negative gross keeps sign
        (-108.10, "-8.10", 8.10),  # both negative -> positive
    ],
)
def test_calc_mwst_extracts_tax_from_gross(betrag, pct, expected):
    assert calc_mwst(betrag, pct) == pytest.approx(expected)


# B-05: the tax portion is rounded half-up (kaufmännisch), not half-even like ``round()``.
# Each gross below is chosen so that betrag * pct / (100 + pct) lands exactly on a half Rappen.
@pytest.mark.parametrize(
    ("betrag", "pct", "expected"),
    [
        (0.125 * 108.1 / 8.1, "8.10", 0.13),  # tax = 0.125 -> 0.13 (round() gives 0.12)
        (0.135 * 108.1 / 8.1, "8.10", 0.14),  # tax = 0.135 -> 0.14
        (2.675 * 108.1 / 8.1, "8.10", 2.68),  # tax = 2.675 -> 2.68 (classic float trap)
        (0.125 * 102.6 / 2.6, "2.60", 0.13),  # reduced rate, same rule
        (2.675 * 102.6 / 2.6, "2.6", 2.68),
        (-(0.125 * 108.1 / 8.1), "8.10", -0.13),  # symmetric for negative gross
        (0.125 * 108.1 / 8.1, "-8.10", -0.13),  # and for a negative rate
        (-(2.675 * 102.6 / 2.6), "-2.60", 2.68),
    ],
)
def test_calc_mwst_rounds_half_up(betrag, pct, expected):
    assert calc_mwst(betrag, pct) == expected
    assert isinstance(calc_mwst(betrag, pct), float)


@pytest.mark.parametrize(("betrag", "pct"), [(100.0, ""), (0, "8.10"), (100.0, "abc"), (None, "8.10")])
def test_calc_mwst_blank_when_not_computable(betrag, pct):
    assert calc_mwst(betrag, pct) == ""


# ── rules layer (deterministic, no DB) ───────────────────────────────────────


def _rules_only() -> TenantClassifier:
    return TenantClassifier(tenant_id=0, db=None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "soll", "haben", "code", "pct"),
    [
        ("Swisscom Abo", "6500", "1020", "I81", "8.10"),
        ("Agrola Tankstelle Diesel", "6210", "1020", "I81", "8.10"),
        ("Miete Büro", "6000", "1020", "", ""),
        ("Nettolohn Mai", "5000", "1020", "", ""),
        ("Google Workspace", "6570", "1020", "I81", "8.10"),
        ("Coop Pronto", "6500", "1020", "", ""),
        ("Gutschrift Kunde", "1020", "3000", "V81", "-8.10"),
        ("Zahlung erhalten", "1020", "1100", "", ""),
    ],
)
def test_rules_map_keywords_to_accounts(text, soll, haben, code, pct):
    result = _rules_only()._classify_rules(text, 100.0)
    assert (result.kt_soll, result.kt_haben, result.mwst_code, result.mwst_pct) == (soll, haben, code, pct)
    assert result.source == "Regeln"


def test_rules_are_case_insensitive():
    assert _rules_only()._classify_rules("SWISSCOM", 10).kt_soll == "6500"


def test_rules_single_keyword_confidence():
    result = _rules_only()._classify_rules("Swisscom", 10)
    assert result.confidence == pytest.approx(RULE_CONFIDENCE)


def test_rules_multiple_keywords_raise_confidence_capped():
    # Two hits in the same rule (+0.08) ...
    two = _rules_only()._classify_rules("Agrola Tankstelle", 10)
    assert two.confidence == pytest.approx(RULE_CONFIDENCE + 0.08)
    # ... and the cap at 0.95 holds however many match.
    many = _rules_only()._classify_rules("tankstelle benzin fuel agrola landi diesel", 10)
    assert many.confidence == pytest.approx(0.95)


def test_rules_first_matching_rule_wins():
    # "software" (6570) is listed before "versicherung" (6300); order is the contract.
    result = _rules_only()._classify_rules("Software Versicherung", 10)
    assert result.kt_soll == "6570"


def test_rules_fallback_is_6500_with_low_confidence():
    result = _rules_only()._classify_rules("xqzv völlig unbekannt", 50.0)
    assert (result.kt_soll, result.kt_haben) == ("6500", "1020")
    assert result.confidence == DEFAULT_RULE_CONFIDENCE
    assert result.mwst_amount == ""


def test_rules_compute_vat_from_rule_rate():
    result = _rules_only()._classify_rules("Swisscom", 108.10)
    assert result.mwst_amount == pytest.approx(8.10)


def test_rule_table_is_well_formed():
    for keywords, soll, haben, code, pct in CLASSIFICATION_RULES:
        assert keywords and all(kw == kw.lower() for kw in keywords)
        assert soll.isdigit() and haben.isdigit()
        assert (code == "") == (pct == "")


# ── credit shortcut ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_credit_is_booked_as_revenue_before_memory(db_session):
    tenant = await create_tenant(db_session)
    await create_memory(db_session, tenant, "Kunde XY", kt_soll="9999")
    clf = await _clf(db_session, tenant.id)

    result = await clf.classify("Kunde XY", True, 216.20)
    assert (result.kt_soll, result.kt_haben, result.mwst_code, result.mwst_pct) == ("1020", "3000", "V81", "-8.10")
    assert result.mwst_amount == pytest.approx(-16.20)
    assert result.confidence == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("betrag", "expected"),
    [
        (0.125 * 108.1 / 8.1, -0.13),  # tax portion 0.125 -> half-up, not round()'s 0.12
        (2.675 * 108.1 / 8.1, -2.68),
        (-(0.125 * 108.1 / 8.1), 0.13),  # a negative credit flips back
    ],
)
async def test_credit_shortcut_rounds_half_up(db_session, betrag, expected):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)
    result = await clf.classify("Gutschrift", True, betrag)
    assert result.mwst_amount == expected


# ── memory layer ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_hit_beats_rules_and_model(db_session):
    tenant = await create_tenant(db_session)
    await create_memory(
        db_session, tenant, "Swisscom Rechnung 2024", kt_soll="6510", kt_haben="2000", mwst_code="I81", mwst_pct="8.10"
    )
    model = FakeModel(["4000"], [0.99])
    clf = await _clf(db_session, tenant.id, model)

    result = await clf.classify("SWISSCOM Rechnung 2025", False, 108.10)
    assert result.source == "Gedächtnis"
    assert result.confidence == 1.0
    assert (result.kt_soll, result.kt_haben, result.mwst_code) == ("6510", "2000", "I81")
    assert result.mwst_amount == pytest.approx(8.10)


@pytest.mark.asyncio
async def test_memory_is_exact_key_match_only(db_session):
    tenant = await create_tenant(db_session)
    await create_memory(db_session, tenant, "Swisscom Rechnung", kt_soll="6510")
    clf = await _clf(db_session, tenant.id)

    result = await clf.classify("Swisscom Rechnung Zusatz", False, 10)
    assert result.source == "Regeln"


@pytest.mark.asyncio
async def test_memory_of_other_tenant_is_invisible(db_session):
    tenant_a = await create_tenant(db_session)
    tenant_b = await create_tenant(db_session)
    await create_memory(db_session, tenant_b, "Geheimlieferant", kt_soll="1234")
    clf = await _clf(db_session, tenant_a.id)

    result = await clf.classify("Geheimlieferant", False, 10)
    assert result.source == "Regeln"
    assert result.kt_soll != "1234"


@pytest.mark.asyncio
async def test_save_to_memory_upserts_and_ignores_blank(db_session):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)

    await clf.save_to_memory("Galaxus 4711", "6500", "1020")
    await clf.save_to_memory("Galaxus 4712", "6570", "1020", "I81", "8.10")
    await clf.save_to_memory("   ", "0000", "0000")
    await db_session.commit()

    rows = (await db_session.execute(select(Memory).where(Memory.tenant_id == tenant.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].lookup_key == make_memory_key("Galaxus")
    assert (rows[0].kt_soll, rows[0].mwst_code) == ("6570", "I81")


# ── ML layer ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ml_prediction_uses_konto_defaults(db_session):
    tenant = await create_tenant(db_session)
    await create_konto_default(db_session, tenant, "6570", "2000", "I81", "8.10")
    model = FakeModel(["4000", "6570"], [0.2, 0.8])
    clf = await _clf(db_session, tenant.id, model)

    result = await clf.classify("Hetzner Cloud 2025", False, 108.10)
    assert result.source == "ML"
    assert result.confidence == pytest.approx(0.8)
    assert (result.kt_soll, result.kt_haben, result.mwst_code, result.mwst_pct) == ("6570", "2000", "I81", "8.10")
    assert result.mwst_amount == pytest.approx(8.10)


@pytest.mark.asyncio
async def test_ml_without_konto_default_falls_back_to_1020(db_session):
    tenant = await create_tenant(db_session)
    model = FakeModel(["6570"], [0.9])
    clf = await _clf(db_session, tenant.id, model)

    result = await clf.classify("Hetzner", False, 100)
    assert (result.kt_haben, result.mwst_code, result.mwst_pct, result.mwst_amount) == ("1020", "", "", "")


@pytest.mark.asyncio
async def test_ml_receives_preprocessed_text(db_session):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)
    model = FakeModel(["6570"], [0.9])
    clf._model = model  # bypass pickling so we can inspect the call

    await clf.classify("Hetzner Cloud 2025", False, 100)
    assert model.seen == ["hetzner cloud"]


@pytest.mark.asyncio
async def test_ml_below_threshold_falls_through_to_rules(db_session):
    tenant = await create_tenant(db_session)
    model = FakeModel(["4000", "6570"], [0.56, 0.44])  # max 0.56 >= 0.45 -> ML
    clf = await _clf(db_session, tenant.id)
    clf._model = model
    assert (await clf.classify("Swisscom", False, 10)).source == "ML"

    clf._model = FakeModel(["4000", "6570"], [0.44, 0.40])  # max 0.44 < 0.45 -> rules
    result = await clf.classify("Swisscom", False, 10)
    assert result.source == "Regeln"
    assert result.kt_soll == "6500"


@pytest.mark.asyncio
async def test_ml_exactly_at_threshold_is_accepted(db_session):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)
    clf._model = FakeModel(["4000", "6570", "6500"], [CONFIDENCE_THRESHOLD, 0.30, 0.25])
    assert (await clf.classify("irgendwas", False, 10)).source == "ML"


@pytest.mark.asyncio
async def test_model_of_other_tenant_is_not_loaded(db_session):
    tenant_a = await create_tenant(db_session)
    tenant_b = await create_tenant(db_session)
    await _clf(db_session, tenant_b.id, FakeModel(["1234"], [0.99]))
    clf = await _clf(db_session, tenant_a.id)

    assert await clf._load_model() is None
    assert (await clf.classify("irgendwas", False, 10)).source == "Regeln"


# ── training (real sklearn, tiny dataset) ────────────────────────────────────


@pytest.mark.asyncio
async def test_train_requires_five_rows(db_session):
    tenant = await create_tenant(db_session)
    for i in range(4):
        await create_training_row(db_session, tenant, f"Zeile {i}", "6500")
    clf = await _clf(db_session, tenant.id)

    result = await clf.train_from_db()
    assert "error" in result
    assert await clf.model_info() is None


@pytest.mark.asyncio
async def test_train_persists_model_and_history_and_is_used(db_session):
    tenant = await create_tenant(db_session)
    await create_konto_default(db_session, tenant, "6570", "1020", "I81", "8.10")
    samples = {
        "hetzner cloud server hosting": "6570",
        "hetzner rechnung hosting": "6570",
        "cloud hosting hetzner": "6570",
        "swisscom telefon abo": "6500",
        "swisscom mobile abo": "6500",
        "telefon swisscom": "6500",
    }
    for text, soll in samples.items():
        await create_training_row(db_session, tenant, text, soll)
    clf = await _clf(db_session, tenant.id)

    result = await clf.train_from_db()
    await db_session.commit()
    assert result["total_samples"] == 6
    assert result["classes"] == 2
    assert result["train_accuracy"] == pytest.approx(1.0)

    row = (await db_session.execute(select(ClassifierModel).where(ClassifierModel.tenant_id == tenant.id))).scalar_one()
    assert row.total_samples == 6 and row.num_classes == 2
    history = (
        (await db_session.execute(select(AccuracyHistory).where(AccuracyHistory.tenant_id == tenant.id)))
        .scalars()
        .all()
    )
    assert len(history) == 1

    # A fresh classifier loads the persisted model and prefers it over the rules.
    fresh = TenantClassifier(tenant.id, db_session)
    ml = await fresh.classify("hetzner hosting", False, 108.10)
    assert ml.source == "ML"
    assert ml.kt_soll == "6570"
    assert ml.mwst_code == "I81"
    assert ml.confidence >= CONFIDENCE_THRESHOLD


# ── corrections ──────────────────────────────────────────────────────────────


def _original(soll="6500", haben="1020") -> ClassificationResult:
    return ClassificationResult(kt_soll=soll, kt_haben=haben, mwst_code="", mwst_pct="", mwst_amount="")


@pytest.mark.asyncio
async def test_log_correction_writes_memory_and_correction(db_session):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)

    await clf.log_correction("Galaxus Bestellung", _original(), "6570", "1020", "I81", "8.10")
    await db_session.commit()

    assert await clf.correction_count() == 1
    assert await clf.memory_count() == 1
    followup = await clf.classify("Galaxus Bestellung 999", False, 108.10)
    assert followup.source == "Gedächtnis"
    assert (followup.kt_soll, followup.mwst_code) == ("6570", "I81")


@pytest.mark.asyncio
async def test_log_correction_confirmation_only_updates_memory(db_session):
    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)

    await clf.log_correction("Galaxus", _original("6570", "1020"), "6570", "1020")
    await db_session.commit()

    assert await clf.memory_count() == 1
    assert await clf.correction_count() == 0


@pytest.mark.asyncio
async def test_auto_retrain_is_enqueued_every_n_corrections(db_session, monkeypatch):
    from app.services import training_worker

    tenant = await create_tenant(db_session)
    clf = await _clf(db_session, tenant.id)
    enqueued: list[int] = []

    class FakeWorker:
        async def enqueue_training(self, tenant_id: int) -> bool:
            enqueued.append(tenant_id)
            return True

    monkeypatch.setattr(training_worker, "get_training_worker", lambda: FakeWorker())

    for i in range(AUTO_RETRAIN_THRESHOLD):
        await clf.log_correction(f"Lieferant {i}", _original(), "6570", "1020")
    await db_session.commit()

    assert (await db_session.execute(select(Correction).where(Correction.tenant_id == tenant.id))).scalars().all()
    assert enqueued == [tenant.id]


# ── review-queue threshold ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_threshold_defaults_and_reads_tenant_config(db_session):
    tenant_default = await create_tenant(db_session)
    tenant_custom = await create_tenant(db_session)
    await create_scanner_config(db_session, tenant_custom, review_confidence_threshold=0.5)

    assert await ReviewQueueService(tenant_default.id, db_session).get_threshold() == DEFAULT_THRESHOLD
    assert await ReviewQueueService(tenant_custom.id, db_session).get_threshold() == 0.5


@pytest.mark.parametrize(
    ("confidence", "threshold", "enqueued"),
    [
        (0.35, 0.80, True),
        (0.79, 0.80, True),
        (0.80, 0.80, False),  # boundary: >= threshold passes without review
        (1.00, 0.80, False),
        (0.60, 0.50, False),
        (0.49, 0.50, True),
    ],
)
@pytest.mark.asyncio
async def test_enqueue_if_low_confidence_respects_threshold(db_session, confidence, threshold, enqueued):
    tenant = await create_tenant(db_session)
    await create_scanner_config(db_session, tenant, review_confidence_threshold=threshold)
    result = ClassificationResult("6500", "1020", "", "", "", confidence=confidence, source="Regeln")

    service = ReviewQueueService(tenant.id, db_session)
    item = await service.enqueue_if_low_confidence("Unklar", 12.0, result)
    await db_session.commit()

    assert (item is not None) is enqueued
    assert await service.pending_count() == (1 if enqueued else 0)
    if item:
        assert (item.predicted_soll, item.confidence, item.source) == ("6500", confidence, "Regeln")


@pytest.mark.asyncio
async def test_end_to_end_unknown_text_lands_in_review_queue(db_session):
    tenant = await create_tenant(db_session)
    await create_user(db_session, tenant)
    clf = await _clf(db_session, tenant.id)

    result = await clf.classify("xqzv völlig unbekannt", False, 12.0)
    item = await ReviewQueueService(tenant.id, db_session).enqueue_if_low_confidence("xqzv", 12.0, result)
    assert item is not None and item.confidence == DEFAULT_RULE_CONFIDENCE
