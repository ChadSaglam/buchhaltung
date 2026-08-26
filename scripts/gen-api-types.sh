#!/usr/bin/env bash
# Regenerate the frontend's API types straight from the FastAPI schema.
# One source of truth: the backend. Run via `make api-types` or `npm run gen:api`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA="$ROOT/backend/openapi.json"
OUT="$ROOT/frontend/src/lib/api-types.ts"

PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x "$ROOT/backend/venv/bin/python" ]]; then PY="$ROOT/backend/venv/bin/python"; else PY="python3"; fi
fi

echo "→ dumping OpenAPI schema…"
(cd "$ROOT/backend" && "$PY" scripts/dump_openapi.py) > "$SCHEMA"

echo "→ generating TypeScript types…"
(cd "$ROOT/frontend" && npx --yes openapi-typescript "$SCHEMA" -o "$OUT")

# Prepend a do-not-edit banner.
TMP="$(mktemp)"
{
  echo "/* eslint-disable */"
  echo "/**"
  echo " * AUTO-GENERATED — do not edit by hand."
  echo " * Source: backend FastAPI OpenAPI schema."
  echo " * Regenerate with: make api-types  (or: npm run gen:api)"
  echo " */"
  cat "$OUT"
} > "$TMP"
mv "$TMP" "$OUT"

echo "✔ $OUT"
