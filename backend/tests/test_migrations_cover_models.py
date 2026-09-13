"""B-39 — every table in `Base.metadata` exists after `alembic upgrade head`, Postgres only.

Guards against the failure mode behind B-39: a model that is importable but
invisible to Alembic (not exported from `app.models`), so `create_all` hides
the missing migration in dev and production 500s on first use.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.models.base import Base
from tests.conftest import _IS_SQLITE, TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(_IS_SQLITE, reason="Alembic chain is verified against Postgres only.")


def test_upgrade_head_creates_every_model_table():
    sync_url = TEST_DATABASE_URL.replace("+asyncpg", "")
    engine = sa.create_engine(sync_url, isolation_level="AUTOCOMMIT")
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}

    with engine.connect() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, env=env, check=True)
        inspector = sa.inspect(engine)
        present = set(inspector.get_table_names())
        missing = set(Base.metadata.tables) - present
        assert not missing, f"models without a migration: {sorted(missing)}"
        assert "ix_training_data_tenant_id" in {ix["name"] for ix in inspector.get_indexes("training_data")}
    finally:
        with engine.connect() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))
        engine.dispose()
