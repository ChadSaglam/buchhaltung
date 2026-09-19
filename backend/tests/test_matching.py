"""Abgleich engine (phase 3) — reference beats amount, amount needs a plausible date,
and a Sammelauftrag is a sum of open invoices. Pure unit tests, no DB."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.matching import (
    TIER_AMOUNT_DATE,
    TIER_REFERENCE,
    TIER_SUBSET,
    DocumentRef,
    TransactionRef,
    find_subsets,
    propose_matches,
    to_cents,
)

QRR = "210000000003139471430009017"


def doc(id_: int, amount: float, *, vendor="", d="2026-04-01", ref="", due=None) -> DocumentRef:
    return DocumentRef(
        id=id_,
        amount=amount,
        vendor=vendor,
        invoice_date=date.fromisoformat(d) if d else None,
        due_date=date.fromisoformat(due) if due else None,
        reference=ref,
    )


def tx(id_: int, amount: float, *, d="2026-04-10", text="E-BANKING-SAMMELAUFTRAG", ref="", party="") -> TransactionRef:
    return TransactionRef(
        id=id_,
        amount=amount,
        value_date=date.fromisoformat(d) if d else None,
        description=text,
        reference=ref,
        counterparty=party,
    )


# ── money as Rappen ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("amount", "cents"),
    [(1949.45, 194945), (-770.60, 77060), (0.1, 10), (None, 0), (87.555, 8756)],
)
def test_to_cents_is_exact_and_absolute(amount, cents):
    assert to_cents(amount) == cents


def test_subset_sums_do_not_drift():
    # 0.1 + 0.2 + 0.3 is 0.6000000000000001 in floats; in Rappen it is 60.
    target = to_cents(0.6)
    subsets = find_subsets(target, [doc(1, 0.1), doc(2, 0.2), doc(3, 0.3)])
    assert [sorted(d.id for d in s) for s in subsets] == [[1, 2, 3]]


# ── tier 1: reference ────────────────────────────────────────────────────────


def test_reference_wins_even_when_another_invoice_has_the_same_amount():
    line = tx(1, -1949.45, ref=QRR)
    right = doc(10, 1949.45, vendor="Cembra", ref=QRR)
    decoy = doc(11, 1949.45, vendor="Irgendwer")
    [p] = propose_matches([line], [right, decoy])
    assert (p.tier, p.document_ids, p.score) == (TIER_REFERENCE, [10], 1.0)
    assert "Referenz stimmt exakt" in p.reason


def test_reference_ignored_when_only_one_side_has_it():
    line = tx(1, -100.0, ref=QRR, d="2026-04-02")
    assert propose_matches([line], [doc(10, 100.0, ref="")])[0].tier == TIER_AMOUNT_DATE
    assert propose_matches([tx(2, -100.0, d="2026-04-02")], [doc(10, 100.0, ref=QRR)])[0].tier == TIER_AMOUNT_DATE


# ── tier 2: amount + date window ─────────────────────────────────────────────


def test_amount_and_date_inside_the_window():
    [p] = propose_matches([tx(1, -770.60, d="2026-04-27", text="E-BANKING-AUFTRAG")], [doc(10, 770.60, d="2026-04-01")])
    assert (p.tier, p.document_ids) == (TIER_AMOUNT_DATE, [10])
    assert p.reason.startswith("Betrag exakt, 26 Tage nach Rechnungsdatum")
    assert 0.7 <= p.score < 0.8  # no vendor text to confirm it


@pytest.mark.parametrize("day", ["2026-03-20", "2026-05-20"])
def test_amount_alone_is_not_enough_outside_the_window(day):
    assert propose_matches([tx(1, -500.0, d=day)], [doc(10, 500.0, d="2026-04-01")]) == []


def test_vendor_text_raises_the_score_and_shows_up_in_the_reason():
    line = tx(1, -250.65, d="2026-04-03", text="ZAHLUNG DEBITKARTE 4397XXXX ISO-Center AG")
    [p] = propose_matches([line], [doc(10, 250.65, vendor="ISO-Center AG", d="2026-04-01")])
    assert p.score >= 0.9
    assert "ISO-Center AG" in p.reason


def test_a_cent_apart_is_not_a_match():
    assert propose_matches([tx(1, -100.02, d="2026-04-02")], [doc(10, 100.0)]) == []


def test_missing_dates_do_not_block_an_exact_amount():
    [p] = propose_matches([tx(1, -40.0, d=None)], [doc(10, 40.0, d=None)])
    assert p.tier == TIER_AMOUNT_DATE
    assert "kein Datum" in p.reason


# ── tier 3: Sammelauftrag (n:1) ──────────────────────────────────────────────


def test_sammelauftrag_splits_one_line_over_several_invoices():
    line = tx(1, -1012.00, d="2026-04-02")
    docs = [doc(10, 87.55, vendor="Die Post"), doc(11, 924.45, vendor="Swisscom"), doc(12, 500.0, vendor="Andere")]
    [p] = propose_matches([line], docs)
    assert p.tier == TIER_SUBSET
    assert sorted(p.document_ids) == [10, 11]
    assert p.amounts == {10: 87.55, 11: 924.45}
    assert p.is_split and "2 offenen Rechnungen" in p.reason


def test_ambiguous_bundles_score_lower_and_say_so():
    # 100 = 60+40 and 100 = 70+30 — the engine must not pretend to know.
    docs = [doc(10, 60.0), doc(11, 40.0), doc(12, 70.0), doc(13, 30.0)]
    [p] = propose_matches([tx(1, -100.0, d="2026-04-05")], docs)
    assert p.tier == TIER_SUBSET
    assert p.score < 0.7
    assert "Kombinationen möglich" in p.reason


def test_a_single_exact_invoice_beats_a_bundle_of_the_same_total():
    docs = [doc(10, 100.0, vendor="Exakt AG"), doc(11, 60.0), doc(12, 40.0)]
    [p] = propose_matches([tx(1, -100.0, d="2026-04-05")], docs)
    assert (p.tier, p.document_ids) == (TIER_AMOUNT_DATE, [10])


def test_credit_lines_never_get_a_bundle_proposal():
    # Money coming in is revenue (or a customer paying us), not a supplier bundle.
    assert propose_matches([tx(1, 1012.00, d="2026-04-02", text="GUTSCHRIFT")], [doc(10, 87.55), doc(11, 924.45)]) == []


# ── no double-spending a document ────────────────────────────────────────────


def test_one_invoice_is_proposed_to_only_one_line_and_the_stronger_one_wins():
    invoice = doc(10, 300.0, vendor="Swiss Life", ref=QRR)
    strong = tx(1, -300.0, d="2026-04-10", ref=QRR)
    weak = tx(2, -300.0, d="2026-04-13")
    proposals = propose_matches([weak, strong], [invoice])
    assert [(p.transaction_id, p.tier) for p in proposals] == [(1, TIER_REFERENCE)]


def test_bundle_does_not_steal_an_invoice_that_a_reference_already_claims():
    docs = [doc(10, 87.55, ref=QRR), doc(11, 924.45)]
    lines = [tx(1, -87.55, d="2026-04-10", ref=QRR), tx(2, -1012.00, d="2026-04-02")]
    proposals = propose_matches(lines, docs)
    assert [(p.transaction_id, sorted(p.document_ids)) for p in proposals] == [(1, [10])]


# ── degenerate input ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("lines", "docs"),
    [([], []), ([tx(1, -10.0)], []), ([], [doc(1, 10.0)]), ([tx(1, 0.0)], [doc(1, 0.0)])],
)
def test_empty_and_zero_input_is_no_proposal(lines, docs):
    assert propose_matches(lines, docs) == []


def test_subsets_are_capped_so_the_search_cannot_explode():
    many = [doc(i, float(i)) for i in range(1, 40)]
    subsets = find_subsets(to_cents(70.0), many)
    assert 0 < len(subsets) <= 4
    assert all(abs(sum(d.cents for d in s) - 7000) <= 1 for s in subsets)
