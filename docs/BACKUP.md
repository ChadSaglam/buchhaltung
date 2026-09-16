# Backup and restore (B-25)

> Until 2026-09-16 there was no backup of any kind. `docs/DEPLOY-CHECKLIST-B36-B37.md`
> still said "do it by hand and record where it went", which is a plan that works
> exactly as long as someone remembers.

## What has to survive

Two things, and both of them:

| | Where it lives | What is lost without it |
|---|---|---|
| **Postgres** | the `pgdata` volume | every booking, document, tenant, payslip and audit entry |
| **`model_data`** | the `model_data` volume | every receipt and bank statement PDF, and the trained model blobs |

A database-only backup restores an application whose documents all 404. That is
not a restore, so the backup takes both and the drill checks both.

## Running it

```bash
docker compose --profile backup up -d backup   # nightly, from now on
make backup                                    # one now
make backup-list                               # what exists
make restore-drill                             # prove the newest one comes back
```

The `backup` service is the `postgres:16-alpine` image, so it already has
`pg_dump` and reaches `db` over the compose network. No docker socket, no host
cron, nothing on the host to forget when the machine is rebuilt. It is behind a
compose profile so a laptop `docker compose up` does not silently start writing
backups.

Backups land in `./backups` (override with `BACKUP_PATH`), one directory per run:

```
backups/20260916T031500Z/
  db.dump         pg_dump -Fc
  files.tar.gz    the model_data tree
  manifest.json   what the two files above should contain
```

`db.dump` is the custom format rather than plain SQL because `pg_restore` can
read it selectively — on the bad day you often want one table, not the whole
database.

## Retention

**30 days by default** (`BACKUP_RETENTION_DAYS`), pruned after each successful
run by `scripts/backup-prune.sh`.

Two rules that are in the code and are there for a reason:

* **The newest backup is never deleted**, whatever the retention is set to. A
  retention of 0 means "keep one", not "keep none".
* **Only directories named like a backup are touched.** Anything else in the
  backup directory — a README, a manual dump, a folder someone parked there — is
  left alone, so pointing the script at the wrong path cannot empty it.

Pruning goes by the timestamp in the directory *name*, not by mtime: a directory
that gets touched by a copy or a sync would otherwise never expire.

`backend/tests/test_backup_scripts.py` covers this against real directories,
because retention logic tested against a mock filesystem is retention logic that
has never deleted anything.

## Why the backup connects as the owner

With B-24's Row-Level Security in place, a dump taken as the application's
`app_rw` role — which has `NOBYPASSRLS` and no `app.tenant_id` set — would
contain **zero rows** from twenty-four tables and exit 0. The backup service
therefore connects as `POSTGRES_USER`, the owner, which policies do not apply to.

The manifest's row counts would catch it either way, which is one more reason
they are in there.

## Off this machine

What is written here is a backup on the same host as the thing it is backing up.
That covers a bad migration, a dropped table and a `docker compose down -v`. It
does not cover the disk, the machine or the datacentre.

Point `BACKUP_PATH` at a mounted network share, or sync `./backups` somewhere
else — `restic`, `rclone`, `borg`, an S3 bucket, whichever. The manifest makes
that safe to do with a dumb file sync: every backup directory is immutable once
written, and the checksums say whether it arrived intact.

## The drill

```bash
make restore-drill
```

Restores the newest backup into a throwaway database, verifies it, and drops it.
It never touches the live database.

What it checks, in the order things actually go wrong:

1. `db.dump` still hashes to what the manifest says — bit rot, a half-finished
   copy, a truncated upload;
2. `pg_restore` completes with `--exit-on-error`;
3. every table in the manifest has the row count that was recorded at dump time
   — this is what catches a dump taken while something was already broken;
4. the schema is at the alembic revision the manifest names;
5. `files.tar.gz` hashes correctly and lists without error.

Run it after every deploy that includes a migration, and once a month otherwise.
A backup nobody has restored is a directory that makes people feel safe.

## Restoring for real

The drill is the rehearsal; this is the performance. Do it deliberately.

```bash
# 1. Stop everything that writes.
docker compose stop api worker web

# 2. Prove the backup is good before destroying anything.
make restore-drill

# 3. Restore the database.
docker compose --profile backup run --rm --entrypoint /bin/sh backup -c '
  psql -h db -U chadev -d postgres -c "DROP DATABASE chadev_buchhaltung" &&
  psql -h db -U chadev -d postgres -c "CREATE DATABASE chadev_buchhaltung" &&
  pg_restore -h db -U chadev -d chadev_buchhaltung --exit-on-error /backups/<stamp>/db.dump'

# 4. Restore the files.
docker compose --profile backup run --rm --entrypoint /bin/sh \
  -v model_data:/restore backup -c 'tar -xzf /backups/<stamp>/files.tar.gz -C /restore'
#    (model_data is mounted read-only in the backup service by design; this
#     command mounts it writable for the one operation that needs to write.)

# 5. Bring it back up. The API entrypoint runs `alembic upgrade head`, so a
#    backup from an older schema migrates forward on start.
docker compose up -d
```

Step 2 is not optional. Dropping the database before knowing the backup restores
is how a recoverable incident becomes a permanent one.

## What this does not do

* **No point-in-time recovery.** A nightly dump means up to 24 hours of bookings
  can be lost. WAL archiving is the answer if that ever becomes unacceptable;
  it is a bigger commitment (a place to stream to, and a restore procedure that
  is no longer one command).
* **No encryption at rest.** The dump contains every tenant's bookkeeping. If
  `BACKUP_PATH` is anywhere other than a disk you already trust with the live
  database, encrypt it on the way out.
* **Nothing is monitored.** The service restarts on failure and logs, but no
  alert fires when a backup has not run for three days. `make backup-list` is
  the manual version of that check.
