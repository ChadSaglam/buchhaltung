#!/bin/sh
# Retention (B-25). Split out of backup.sh because it is the only part that
# deletes, and therefore the only part worth testing on its own — see
# backend/tests/test_backup_scripts.py.
#
# Deletes backup directories older than N days, by their *name*, which is the
# UTC timestamp the backup was taken at. Deliberately not by mtime: a directory
# that gets touched by a copy or a sync would otherwise live forever.
#
# Two refusals that matter:
#   * anything that is not a <stamp> directory is left alone — this script must
#     never be able to empty a directory somebody pointed it at by mistake;
#   * the newest backup is never deleted, whatever the retention. A retention of
#     0 means "keep one", not "keep none".
#
# Usage: backup-prune.sh <dir> <days>
set -eu

DIR="${1:?usage: backup-prune.sh <dir> <days>}"
DAYS="${2:-30}"

[ -d "$DIR" ] || exit 0

# YYYYmmddTHHMMSSZ, nothing else.
stamps=$(ls -1 "$DIR" 2>/dev/null \
  | grep -E '^[0-9]{8}T[0-9]{6}Z$' \
  | sort) || stamps=""
[ -n "$stamps" ] || exit 0

newest=$(echo "$stamps" | tail -n 1)

# The cut-off as the same kind of string, so the comparison is lexicographic and
# needs no date arithmetic in sh. GNU and BSD date disagree on the flag.
cutoff=$(date -u -d "-${DAYS} days" +%Y%m%dT%H%M%SZ 2>/dev/null \
  || date -u -v-"${DAYS}"d +%Y%m%dT%H%M%SZ 2>/dev/null \
  || echo "")
[ -n "$cutoff" ] || { echo "[prune] cannot compute a cut-off date; keeping everything" >&2; exit 0; }

echo "$stamps" | while IFS= read -r stamp; do
  [ "$stamp" = "$newest" ] && continue
  [ "$stamp" \< "$cutoff" ] || continue
  echo "[prune] removing $stamp" >&2
  rm -rf "$DIR/$stamp"
done
