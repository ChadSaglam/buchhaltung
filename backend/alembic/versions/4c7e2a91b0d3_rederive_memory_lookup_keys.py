"""re-derive memory.lookup_key after the preprocess word-boundary fix (B-04)

`memory.lookup_key` is `classifier.preprocess(beschreibung)`. Until B-04 the
function stripped month abbreviations as bare substrings, so "E-Mail" became
"e-l" and "Julia Novak" became "ia ak". The fixed function only strips whole
words, which changes the key of every text that contained such a substring.

Both directions are data-only (no schema change) and self-contained: the old
and the new implementation live in this file so the migration keeps working
when `app.services.classifier` moves on.

Upgrade — for each row the source text is recovered from the most recent
`corrections.beschreibung` of the same tenant whose *legacy* key equals the
row's current key (that is where `log_correction` wrote the memory entry
from); the new key is `_preprocess_new(text)`. Rows without such a correction
(CSV imports, `save_to_memory` calls) get `_preprocess_new(lookup_key)` — a
no-op for keys the old function did not damage, since nothing can be recovered
for the rest.

Downgrade — every key becomes `_preprocess_legacy(lookup_key)`.

Duplicate rule (both directions) — when several rows of one tenant end up on
the same key, the row with the **highest id** wins (the table has neither a
timestamp nor a hit counter, so the highest id is the most recently learned
entry, matching the "last correction wins" semantics of `save_to_memory`);
the others are deleted. Keys are rewritten in two passes through a temporary
per-row value so the unique constraint `uq_tenant_memory` is never hit by a
transient collision (A→"y" while B still holds "y").

Revision ID: 4c7e2a91b0d3
Revises: 921d958b8530
Create Date: 2026-09-10 14:02:00.000000
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "4c7e2a91b0d3"
down_revision: Union[str, None] = "921d958b8530"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── the two implementations (frozen copies, do not import from app) ──────────

_MONTH_RE_NEW = re.compile(
    r"\b(?:januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember"
    r"|jan|feb|mär|mrz|apr|jun|jul|aug|sep|sept|okt|nov|dez)\b\.?"
)


def _preprocess_new(text: str) -> str:
    text = (text or "").lower().strip()
    text = _MONTH_RE_NEW.sub("", text)
    text = re.sub(r"\d", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _preprocess_legacy(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(
        r"(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)",
        "",
        text,
    )
    text = re.sub(r"(jan|feb|mr|apr|jun|jul|aug|sep|okt|nov|dez)", "", text)
    text = re.sub(r"[\d]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── shared machinery ─────────────────────────────────────────────────────────

_SELECT_MEMORY = sa.text("SELECT id, tenant_id, lookup_key FROM memory ORDER BY id")
_SELECT_CORRECTIONS = sa.text("SELECT id, tenant_id, beschreibung FROM corrections ORDER BY id")
_UPDATE_KEY = sa.text("UPDATE memory SET lookup_key = :key WHERE id = :id")
_DELETE_ROW = sa.text("DELETE FROM memory WHERE id = :id")


def _rekey(derive: Callable[[int, int, str], str]) -> None:
    """Rewrite every key with ``derive(id, tenant_id, key)``; collapse duplicates (highest id wins)."""
    conn = op.get_bind()
    rows = conn.execute(_SELECT_MEMORY).all()

    winners: dict[tuple[int, str], int] = {}  # (tenant_id, new_key) -> id
    new_keys: dict[int, str] = {}
    losers: list[int] = []
    for row_id, tenant_id, key in rows:
        new_key = derive(row_id, tenant_id, key)
        new_keys[row_id] = new_key
        slot = (tenant_id, new_key)
        previous = winners.get(slot)
        if previous is not None:
            losers.append(previous)  # rows are id-ordered, the later one wins
        winners[slot] = row_id

    for row_id in losers:
        conn.execute(_DELETE_ROW, {"id": row_id})

    changed = [row_id for row_id, _, key in rows if row_id not in losers and new_keys[row_id] != key]
    # Derived keys never contain digits (both functions strip them), so a
    # digit-bearing placeholder cannot collide with any real key.
    for row_id in changed:
        conn.execute(_UPDATE_KEY, {"id": row_id, "key": f"#migrating#{row_id}"})
    for row_id in changed:
        conn.execute(_UPDATE_KEY, {"id": row_id, "key": new_keys[row_id]})


def upgrade() -> None:
    conn = op.get_bind()
    # (tenant_id, legacy key) -> most recent source text, from the corrections log.
    sources: dict[tuple[int, str], str] = {}
    for _, tenant_id, beschreibung in conn.execute(_SELECT_CORRECTIONS).all():
        if beschreibung:
            sources[(tenant_id, _preprocess_legacy(beschreibung))] = beschreibung

    def derive(_row_id: int, tenant_id: int, key: str) -> str:
        text = sources.get((tenant_id, key))
        return _preprocess_new(text if text is not None else key)

    _rekey(derive)


def downgrade() -> None:
    _rekey(lambda _row_id, _tenant_id, key: _preprocess_legacy(key))
