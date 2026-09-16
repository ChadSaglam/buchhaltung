"""B-56 — the parser and the shared rules, where a small mistake is silent.

Everything here shares one property: it produces a *plausible* wrong answer.
A booking dated 3924, a supplier classified as salary, a memory row that
matches everything — none of them raise, and none of them look wrong in a list.
"""

from __future__ import annotations

import pytest

from app.services.classifier import (
    CLASSIFICATION_RULES,
    VERBOTENE_KEYWORDS,
    TenantClassifier,
    key_ist_brauchbar,
    make_memory_key,
)
from app.services.pdf_parser import parse_statement_date
from tests.factories import create_memory, create_tenant

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------- #
# The date on a bank statement
# --------------------------------------------------------------------------- #


async def test_a_four_digit_year_is_read_as_itself_not_as_the_year_3924():
    """The old pattern was unanchored, so 31.12.2024 matched on its first eight
    characters and the two-digit rule then read 2024 as the year: 1900 + 2024."""
    assert parse_statement_date("31.12.2024") == "31.12.2024"


async def test_a_two_digit_year_still_works():
    """UBS prints dd.mm.yy, which is the format this parser was written for."""
    assert parse_statement_date("05.04.26") == "05.04.2026"


async def test_the_century_cut_off_is_at_fifty():
    assert parse_statement_date("01.01.49") == "01.01.2049"
    assert parse_statement_date("01.01.50") == "01.01.1950"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Datum",
        "31.12",
        "31.12.202",
        "31.12.20245",
        "1.1.2024",
        "31.12.2024 Migros",
        "Total 31.12.2024",
        "31-12-2024",
    ],
)
async def test_what_is_not_a_date_is_not_a_date(text):
    assert parse_statement_date(text) is None


async def test_an_impossible_month_is_not_a_date():
    assert parse_statement_date("31.13.2024") is None
    assert parse_statement_date("00.01.2024") is None


async def test_whitespace_around_a_date_is_fine():
    assert parse_statement_date("  05.04.26  ") == "05.04.2026"


# --------------------------------------------------------------------------- #
# The shared rules belong to everybody
# --------------------------------------------------------------------------- #


def _alle_keywords() -> list[str]:
    return [kw for keywords, *_ in CLASSIFICATION_RULES for kw in keywords]


async def test_no_customers_supplier_is_in_the_shared_rules():
    """A keyword here classifies for a tenant who has never heard of it. The
    worst one was a surname in the payroll rule: any invoice from a supplier of
    that name was booked to 5000 Lohn, for everyone."""
    drin = sorted(k for k in _alle_keywords() if k.strip().lower() in VERBOTENE_KEYWORDS)

    assert drin == [], f"named companies back in the shared rules: {drin}"


async def test_the_forbidden_list_is_not_empty():
    """A guard that guards nothing passes forever."""
    assert len(VERBOTENE_KEYWORDS) >= 5


async def test_every_keyword_is_lowercase():
    """They are matched against a lowercased description; an uppercase entry
    would simply never fire, and nothing would say so."""
    assert [k for k in _alle_keywords() if k != k.lower()] == []


async def test_no_keyword_is_empty_or_whitespace():
    """An empty keyword is in every description."""
    assert [k for k in _alle_keywords() if not k.strip()] == []


async def test_the_generic_vocabulary_survived():
    """The point was to remove names, not to weaken the rules."""
    keywords = set(_alle_keywords())
    for erwartet in ("benzin", "werkzeug", "versicherung", "lohn", "miete", "software"):
        assert erwartet in keywords


async def test_a_supplier_that_used_to_be_hardcoded_now_falls_through(db_session):
    """It should reach the default account, not somebody else's payroll."""
    tenant = await create_tenant(db_session)

    result = await TenantClassifier(tenant.id, db_session).classify("Aksoy Handels GmbH Rechnung", False, 250.0)

    assert result.kt_soll != "5000"


# --------------------------------------------------------------------------- #
# An empty memory key is not a key
# --------------------------------------------------------------------------- #


async def test_a_description_that_reduces_to_nothing_has_no_usable_key():
    """`preprocess` removes digits and month names but not punctuation, so the
    check has to be "does this carry any information", not "is it empty"."""
    assert make_memory_key("2024 03") == ""
    assert make_memory_key("31.12.") == "..", "punctuation survives — this is why"

    assert not key_ist_brauchbar(make_memory_key("2024 03"))
    assert not key_ist_brauchbar(make_memory_key("31.12."))
    assert not key_ist_brauchbar(make_memory_key("   "))
    assert key_ist_brauchbar(make_memory_key("Migros Zürich"))


async def test_a_punctuation_only_key_is_never_written(db_session):
    from sqlalchemy import select

    from app.models.memory import Memory

    tenant = await create_tenant(db_session)
    await TenantClassifier(tenant.id, db_session).save_to_memory("31.12.", "6500", "1020")
    await db_session.flush()

    rows = (await db_session.execute(select(Memory).where(Memory.tenant_id == tenant.id))).scalars().all()
    assert rows == []


async def test_nothing_is_remembered_under_an_empty_key(db_session):
    from sqlalchemy import select

    from app.models.memory import Memory

    tenant = await create_tenant(db_session)
    clf = TenantClassifier(tenant.id, db_session)

    await clf.save_to_memory("2024 03", "6500", "1020")
    await db_session.flush()

    rows = (await db_session.execute(select(Memory).where(Memory.tenant_id == tenant.id))).scalars().all()
    assert rows == []


async def test_a_real_description_is_still_remembered(db_session):
    from sqlalchemy import select

    from app.models.memory import Memory

    tenant = await create_tenant(db_session)
    clf = TenantClassifier(tenant.id, db_session)

    await clf.save_to_memory("Migros Zürich", "6500", "1020")
    await db_session.flush()

    rows = (await db_session.execute(select(Memory).where(Memory.tenant_id == tenant.id))).scalars().all()
    assert len(rows) == 1


async def test_an_old_empty_key_row_cannot_classify_anything(db_session):
    """A row written before the fix would otherwise match every description that
    also reduces to nothing — one row classifying a whole class of bank lines."""
    from app.models.memory import Memory

    tenant = await create_tenant(db_session)
    db_session.add(Memory(tenant_id=tenant.id, lookup_key="", kt_soll="9999", kt_haben="1020"))
    await db_session.flush()

    result = await TenantClassifier(tenant.id, db_session).classify("2026 04", False, 12.0)

    assert result.kt_soll != "9999"


async def test_memory_still_wins_for_a_real_key(db_session):
    tenant = await create_tenant(db_session)
    await create_memory(db_session, tenant, "Migros Zürich", kt_soll="6510")

    result = await TenantClassifier(tenant.id, db_session).classify("Migros Zürich", False, 42.0)

    assert result.kt_soll == "6510"
    assert result.source == "Gedächtnis"
