#!/bin/sh
# Backup: the database and the files (B-25).
#
# Two things have to survive: Postgres, and the `model_data` volume — receipts,
# statements and the trained model blobs. A dump without the files restores an
# app whose documents all 404, which is not a restore.
#
# Writes into $BACKUP_DIR/<UTC timestamp>/:
#
#   db.dump        pg_dump -Fc (custom format: compressed, and pg_restore can
#                  read it selectively, which plain SQL cannot)
#   files.tar.gz   the model_data tree
#   manifest.json  what is in the two files above, and what a restore must find
#
# The manifest is the point. A backup nobody verifies is a directory that makes
# people feel safe; the row counts and checksums in here are what restore-drill
# compares against, so a silently truncated dump fails loudly at drill time
# rather than quietly on the day it is needed.
#
# POSIX sh on purpose: this has to run in the postgres:16-alpine image, which
# has no bash.
#
# Usage:  scripts/backup.sh            one backup, then exit
#         scripts/backup.sh loop       one backup every BACKUP_INTERVAL_SECONDS
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-chadev}"
PGDATABASE="${PGDATABASE:-chadev_buchhaltung}"
FILES_DIR="${FILES_DIR:-/data/model_data}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

# Counted in the manifest and checked by the drill. Not every table — the ones
# whose loss is the reason this script exists.
TABLES="tenants users bookings documents memory corrections lohnabrechnungen mitarbeiter"

log() { echo "[backup] $*" >&2; }

checksum() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

psql_value() {
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tAc "$1" 2>/dev/null || echo ""
}

one_backup() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  target="$BACKUP_DIR/$stamp"
  mkdir -p "$target"
  log "→ $target"

  # --- database -------------------------------------------------------------
  # Into a .part first: a crash mid-dump must not leave a file that looks like
  # a backup. The rename is the commit.
  pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$target/db.dump.part"
  mv "$target/db.dump.part" "$target/db.dump"

  # --- files ----------------------------------------------------------------
  if [ -d "$FILES_DIR" ]; then
    tar -czf "$target/files.tar.gz.part" -C "$FILES_DIR" .
    mv "$target/files.tar.gz.part" "$target/files.tar.gz"
  else
    log "! $FILES_DIR not mounted — files are NOT in this backup"
    : > "$target/files.tar.gz.missing"
  fi

  # --- manifest -------------------------------------------------------------
  revision=$(psql_value "SELECT version_num FROM alembic_version LIMIT 1")
  pgversion=$(psql_value "SHOW server_version")
  {
    printf '{\n'
    printf '  "created_at": "%s",\n' "$stamp"
    printf '  "database": "%s",\n' "$PGDATABASE"
    printf '  "alembic_revision": "%s",\n' "$revision"
    printf '  "postgres_version": "%s",\n' "$pgversion"
    printf '  "db_dump_sha256": "%s",\n' "$(checksum "$target/db.dump")"
    printf '  "db_dump_bytes": %s,\n' "$(wc -c < "$target/db.dump" | tr -d ' ')"
    if [ -f "$target/files.tar.gz" ]; then
      printf '  "files_sha256": "%s",\n' "$(checksum "$target/files.tar.gz")"
      printf '  "files_bytes": %s,\n' "$(wc -c < "$target/files.tar.gz" | tr -d ' ')"
    else
      printf '  "files_sha256": null,\n'
      printf '  "files_bytes": null,\n'
    fi
    printf '  "row_counts": {'
    first=1
    for table in $TABLES; do
      count=$(psql_value "SELECT count(*) FROM $table")
      [ -n "$count" ] || continue
      [ $first -eq 1 ] || printf ','
      printf '\n    "%s": %s' "$table" "$count"
      first=0
    done
    printf '\n  }\n}\n'
  } > "$target/manifest.json.part"
  mv "$target/manifest.json.part" "$target/manifest.json"

  log "✔ $stamp  db $(wc -c < "$target/db.dump" | tr -d ' ') bytes, revision ${revision:-unknown}"
  sh "$(dirname "$0")/backup-prune.sh" "$BACKUP_DIR" "$RETENTION_DAYS"
}

if [ "${1:-once}" = "loop" ]; then
  log "every ${INTERVAL}s, keeping ${RETENTION_DAYS} days"
  while true; do
    one_backup || log "! backup failed, retrying next interval"
    sleep "$INTERVAL"
  done
else
  one_backup
fi
