"""B-04 — the `memory.lookup_key` data migration (4c7e2a91b0d3), Postgres only.

Seeds three memory rows through the legacy key function, one of them a
collision after re-derivation, runs `alembic upgrade head` / `downgrade <B-04 base>` /
`upgrade head` in a subprocess (like test_tenant_contract.py) and checks the
keys and the duplicate rule (highest id wins).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.services.classifier import preprocess
from tests.conftest import _IS_SQLITE, TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "921d958b8530"

pytestmark = pytest.mark.skipif(_IS_SQLITE, reason="Alembic chain is verified against Postgres only.")


def _legacy_key(text: str) -> str:
    """What `preprocess()` produced before B-04 (bare substring month stripping)."""
    text = (text or "").lower().strip()
    text = re.sub(r"(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)", "", text)
    text = re.sub(r"(jan|feb|mr|apr|jun|jul|aug|sep|okt|nov|dez)", "", text)
    text = re.sub(r"[\d]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def test_legacy_key_reproduces_the_old_damage():
    assert _legacy_key("E-Mail Hosting 2025") == "e-l hosting"
    assert preprocess("E-Mail Hosting 2025") == "e-mail hosting"


def test_memory_lookup_keys_are_rederived_and_collisions_collapse():
    sync_url = TEST_DATABASE_URL.replace("+asyncpg", "")
    engine = sa.create_engine(sync_url, isolation_level="AUTOCOMMIT")
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}

    def alembic(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND_DIR, env=env, check=True)

    def reset() -> None:
        with engine.connect() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))

    def memory() -> list[tuple[int, str, str]]:
        with engine.connect() as conn:
            return [tuple(r) for r in conn.execute(sa.text("SELECT id, lookup_key, kt_soll FROM memory ORDER BY id"))]

    reset()
    try:
        alembic("upgrade", PREVIOUS_REVISION)
        with engine.begin() as conn:
            conn.execute(sa.text("INSERT INTO tenants (name, subscription_plan) VALUES ('Alt AG', 'free')"))
            tid = conn.execute(sa.text("SELECT id FROM tenants")).scalar_one()
            # Rows 1 and 2 were learned through log_correction(), so their source text is in
            # `corrections`; row 3 came from a CSV import and has no source text.
            for text, soll in [("E-Mail Hosting 2025", "6570"), ("Miete Feb. 2025", "6000")]:
                conn.execute(
                    sa.text(
                        "INSERT INTO corrections (tenant_id, beschreibung, original_soll, original_haben, "
                        "corrected_soll, corrected_haben, corrected_mwst_code, corrected_mwst_pct, created_at) "
                        "VALUES (:t, :b, '6500', '1020', :s, '1020', '', '', now())"
                    ),
                    {"t": tid, "b": text, "s": soll},
                )
            seeds = [
                ("E-Mail Hosting 2025", "6570"),  # legacy "e-l hosting"  -> "e-mail hosting"
                ("Miete Feb. 2025", "6000"),  # legacy "miete ."  -> "miete"  (collides with row 3)
                ("Miete 2025", "6010"),  # legacy "miete"    -> "miete"  (unchanged, highest id)
            ]
            for text, soll in seeds:
                conn.execute(
                    sa.text(
                        "INSERT INTO memory (tenant_id, lookup_key, kt_soll, kt_haben, mwst_code, mwst_pct) "
                        "VALUES (:t, :k, :s, '1020', '', '')"
                    ),
                    {"t": tid, "k": _legacy_key(text), "s": soll},
                )
        assert memory() == [(1, "e-l hosting", "6570"), (2, "miete .", "6000"), (3, "miete", "6010")]

        alembic("upgrade", "head")
        # Row 1 repaired from its correction text; rows 2 and 3 collapse onto "miete" and the
        # highest id (the most recently learned entry) wins.
        assert memory() == [(1, "e-mail hosting", "6570"), (3, "miete", "6010")]

        alembic("downgrade", PREVIOUS_REVISION)  # below B-04, whatever sits above it
        assert memory() == [(1, "e-l hosting", "6570"), (3, "miete", "6010")]

        alembic("upgrade", "head")
        assert memory() == [(1, "e-mail hosting", "6570"), (3, "miete", "6010")]
    finally:
        reset()
        engine.dispose()
