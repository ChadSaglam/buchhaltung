#!/usr/bin/env sh
# Apply pending Alembic migrations, then hand over to the API server.
# Alembic owns the schema in every non-dev deployment (AGENTS.md rule 3).
set -eu

echo "→ alembic upgrade head"
alembic upgrade head

exec "$@"
