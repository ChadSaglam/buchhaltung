#!/bin/sh
# Restore drill (B-25).
#
# The only question a backup has to answer is "can we come back from it", and
# the only way to know is to do it. This restores a backup into a throwaway
# database and checks it against the manifest that was written at dump time.
#
# It never touches the live database. The scratch database is created, restored,
# checked and dropped; if the script dies in the middle, the leftover is named
# so obviously that nobody mistakes it for the real one.
#
# What it verifies, in the order things actually go wrong:
#   1. the dump file still hashes to what the manifest says (bit rot, a
#      half-finished copy, a truncated upload);
#   2. pg_restore completes without errors;
#   3. every table in the manifest has the row count the manifest recorded —
#      this is what catches a dump that was taken while something was broken;
#   4. the schema is at the alembic revision the manifest names;
#   5. the files archive lists without error and hashes correctly.
#
# Usage: scripts/restore-drill.sh [backup-directory]
#        (default: the newest one under $BACKUP_DIR)
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-chadev}"
DRILL_DB="${DRILL_DB:-restore_drill_scratch}"

log() { echo "[drill] $*" >&2; }
fail() { echo "[drill] ✘ $*" >&2; exit 1; }

checksum() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

# One value out of the flat manifest. jq is not in postgres:16-alpine.
manifest_value() {
  sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\{0,1\}\([^\",}]*\)\"\{0,1\},\{0,1\}.*/\1/p" "$1" | head -n 1
}

manifest_counts() {
  # The `[0-9][0-9]*` is not padding: without it the `"row_counts": {` line
  # itself matches with an empty count, and every table then "differs".
  sed -n '/"row_counts"/,/}/p' "$1" \
    | sed -n 's/.*"\([a-z_]*\)"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1 \2/p'
}

psql_scratch() {
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DRILL_DB" -tAc "$1"
}

backup="${1:-}"
if [ -z "$backup" ]; then
  newest=$(ls -1 "$BACKUP_DIR" 2>/dev/null | grep -E '^[0-9]{8}T[0-9]{6}Z$' | sort | tail -n 1) || newest=""
  [ -n "$newest" ] || fail "no backup found under $BACKUP_DIR"
  backup="$BACKUP_DIR/$newest"
fi
[ -f "$backup/db.dump" ] || fail "$backup/db.dump is missing"
[ -f "$backup/manifest.json" ] || fail "$backup/manifest.json is missing — nothing to verify against"
log "restoring $backup"

# 1 — the dump is the dump we wrote.
expected=$(manifest_value "$backup/manifest.json" db_dump_sha256)
actual=$(checksum "$backup/db.dump")
[ "$expected" = "$actual" ] || fail "db.dump checksum differs (manifest $expected, file $actual)"
log "✔ checksum"

# 2 — restore into a scratch database.
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "DROP DATABASE IF EXISTS $DRILL_DB" >/dev/null
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "CREATE DATABASE $DRILL_DB" >/dev/null
trap 'psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "DROP DATABASE IF EXISTS $DRILL_DB" >/dev/null 2>&1 || true' EXIT
pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DRILL_DB" --exit-on-error "$backup/db.dump" \
  || fail "pg_restore reported errors"
log "✔ pg_restore"

# 3 — every table has what it had.
manifest_counts "$backup/manifest.json" | while read -r table expected_count; do
  [ -n "$table" ] || continue
  actual_count=$(psql_scratch "SELECT count(*) FROM $table" 2>/dev/null || echo "missing")
  if [ "$actual_count" != "$expected_count" ]; then
    echo "[drill] ✘ $table: manifest $expected_count, restored $actual_count" >&2
    exit 1
  fi
  echo "[drill]   $table $actual_count" >&2
done || fail "row counts do not match the manifest"
log "✔ row counts"

# 4 — the schema is where it was.
expected_rev=$(manifest_value "$backup/manifest.json" alembic_revision)
actual_rev=$(psql_scratch "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null || echo "")
if [ -n "$expected_rev" ] && [ "$expected_rev" != "$actual_rev" ]; then
  fail "alembic revision differs (manifest $expected_rev, restored ${actual_rev:-none})"
fi
log "✔ schema at ${actual_rev:-unknown}"

# 5 — the files. A database-only restore leaves every receipt a 404.
if [ -f "$backup/files.tar.gz" ]; then
  expected_files=$(manifest_value "$backup/manifest.json" files_sha256)
  actual_files=$(checksum "$backup/files.tar.gz")
  [ "$expected_files" = "$actual_files" ] || fail "files.tar.gz checksum differs"
  tar -tzf "$backup/files.tar.gz" >/dev/null || fail "files.tar.gz does not list"
  log "✔ files"
else
  log "! this backup has no files archive — receipts would not come back"
fi

log "✔ drill passed for $backup"
