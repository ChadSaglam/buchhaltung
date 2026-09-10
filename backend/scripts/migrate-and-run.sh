#!/usr/bin/env sh
# Bring the schema to Alembic head, then hand over to the given command.
# Used as the Docker ENTRYPOINT and by scripts/dev.sh (`... true` = migrate only).
# Alembic owns the schema in every non-dev deployment (AGENTS.md rule 3).
#
# Volumes created before this entrypoint existed hold tables made by
# `create_all` and no `alembic_version` row. Upgrading such a database would
# fail on "table already exists", so stamp it first at the revision its
# schema actually matches, then upgrade normally.
set -eu

stamp=$(python - <<'PY'
import asyncio, os
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

url = os.environ.get("DATABASE_URL", "")
if not url:
    raise SystemExit(0)

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        def probe(sync_conn):
            insp = inspect(sync_conn)
            tables = set(insp.get_table_names())
            if "alembic_version" in tables or "tenants" not in tables:
                return ""
            cols = {c["name"] for c in insp.get_columns("tenants")}
            # Schema from the current models → head; older create_all schema →
            # last revision before the tenant-contract migration.
            return "head" if "subscription_plan" in cols else "73f03c35bbed"
        print(await conn.run_sync(probe))
    await engine.dispose()

asyncio.run(main())
PY
)

if [ -n "$stamp" ]; then
  echo "→ legacy create_all schema detected, alembic stamp $stamp"
  alembic stamp "$stamp"
fi

echo "→ alembic upgrade head"
alembic upgrade head

exec "$@"
