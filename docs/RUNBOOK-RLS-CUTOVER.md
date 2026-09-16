# Runbook: turning Row-Level Security on in a live deployment (B-24 / ADR-002 item 8)

ADR-002's last open action item reads: *"Canary: deploy one replica, watch for empty-list regressions for 24 h,
then flip all."* This is that step, written for the deployment that actually exists.

**The honest correction first.** There are no replicas. Production is `docker compose` with one `api` service
(that is why `compose-smoke` exists in CI). "One replica" cannot be done here, and pretending otherwise would mean
following a procedure that never matches the screen. What *can* be done, and is what this runbook describes, is a
staged cutover in which the dangerous half is reversible in one command and the silent failure mode has a detector
pointed at it for 24 h.

Read ADR-002 first. This file assumes it.

**What has been checked against a running stack (2026-09-16).** The compose stack was brought up end to end for
the first time, and the state below was read off the live database rather than reasoned about:

- `app_rw` is `rolsuper = f, rolbypassrls = f, rolcanlogin = t`. The owner, `chadev`, is `rolsuper = t` — which is
  section 5's trap, confirmed rather than predicted.
- 24 tables, all `relrowsecurity = t`, all `relforcerowsecurity = t`, 24 policies. Nothing half-covered.
- `pg_stat_activity` showed the API's connections as `app_rw` and only the migration's as the owner.
- As `app_rw` with no tenant context, `INSERT INTO bookings …` was refused with
  `new row violates row-level security policy for table "bookings"`. Fail-closed, live.

That was a fresh database on x86_64. It tells you the mechanism works; it tells you nothing about a database that
already has rows in it, which is what section 4 is for.

---

## 1. What can go wrong, in two very different flavours

**Loud.** A write that violates the policy raises `new row violates row-level security policy for table "…"`.
An import, a booking, an upload fails with a 500. Ugly, obvious, in the logs within minutes.

**Silent, and the reason this runbook exists.** A read with no tenant context does not fail. `current_setting`
returns NULL, `tenant_id = NULL` is never true, and the query returns **zero rows**. The UI renders an empty state.
Nobody gets an error e-mail. The user sees "Keine Belege" on a screen that had 400 of them yesterday.

Every code path that opens its own session has to set the context. Four do today; `test_rls.py` fails the suite
when a fifth appears and is not accounted for. That test is the reason this cutover is worth attempting at all —
but it runs against the code, not against the deployment, and a deployment can be wrong in ways the code is not:
the wrong role in `DATABASE_URL`, a migration that only half ran, a pooler that reuses a session across requests.

---

## 2. Pre-flight — four questions, answered against the live database

Run as the owner (`MIGRATION_DATABASE_URL`'s user), before anything changes.

```sql
-- (a) Does the app's role exist, and is it actually subject to policies?
SELECT rolname, rolsuper, rolbypassrls, rolcanlogin
  FROM pg_roles WHERE rolname IN ('app_rw', current_user);
-- app_rw must be: rolsuper = f, rolbypassrls = f, rolcanlogin = t.
-- If it does not exist, run docker/db-init/10-app-role.sql by hand — the compose
-- `db` service runs that directory only once, on an empty data directory.

-- (b) Which tables are covered, and are any covered only halfway?
SELECT c.relname,
       c.relrowsecurity   AS enabled,
       c.relforcerowsecurity AS forced,
       count(p.polname)   AS policies
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
  LEFT JOIN pg_policy p ON p.polrelid = c.oid
 WHERE c.relkind = 'r'
 GROUP BY 1, 2, 3
 ORDER BY enabled, c.relname;
-- Compare against RLS_TABLES in backend/app/core/rls.py (24 tables) plus the two
-- documented exemptions. `enabled = t, policies = 0` is the worst row you can see:
-- it means every read returns nothing.

-- (c) Is anything still connecting as a role that bypasses all of this?
SELECT usename, count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY 1;

-- (d) Are the two URLs actually two different users?
--     Production refuses to boot when MIGRATION_DATABASE_URL is empty or equal to
--     DATABASE_URL, but it cannot tell you they point at the same *role*.
```

Also confirm from the application side: `GET /api/health` is 200, `GET /api/health/live` is 200, and a backup
exists that is **younger than this change** — see `docs/BACKUP.md`, and restore it once into a scratch database
first. B-25 built the drill; this is the day to have used it.

---

## 3. The cutover

The lever is not the migration — it flips all 24 tables at once for everybody. The lever is **`FORCE`**, because
Postgres exempts a table's owner from its own policies unless `FORCE` is set. That gives exactly two live states
worth having:

| State | Owner connection (`chadev`) | `app_rw` connection |
|---|---|---|
| `ENABLE`, `NO FORCE` | exempt — behaves as before | fully enforced |
| `ENABLE`, `FORCE` | enforced | fully enforced |

So:

1. **Apply the migration.** `scripts/migrate-and-run.sh` runs it as the owner. It lands `ENABLE` + `FORCE` +
   one policy per table.
2. **Step `FORCE` back off** for the duration of the watch. This is the rollback lever, kept within reach:

   ```sql
   DO $$ DECLARE t text;
   BEGIN FOR t IN SELECT unnest(ARRAY[ /* RLS_TABLES from core/rls.py */ ])
        LOOP EXECUTE format('ALTER TABLE %I NO FORCE ROW LEVEL SECURITY', t); END LOOP;
   END $$;
   ```
3. **Point the app at `app_rw`** (`DATABASE_URL`) and restart it. From here the application is fully enforced;
   an operator's `psql` session as the owner is not. That asymmetry is deliberate: it keeps a diagnostic path open
   that cannot itself be the thing that is broken.
4. **Watch for 24 h** (section 4).
5. **Turn `FORCE` back on** for all 24 tables. Now the owner is enforced too, and an operator session no longer
   sees across tenants. This is the state ADR-002 describes; until step 5 the ADR is not implemented.

Note what step 3 costs: production **already refuses to boot** as a superuser or a `BYPASSRLS` role
(`verify_rls_role()`), and the compose `db` service creates `POSTGRES_USER` as a superuser. There is therefore no
version of this deployment where the API runs as the owner in production. Step 3 is not a switch from one working
state to another — it is the first time the app runs as `app_rw` at all. Treat it as the risky step, not step 1.

---

## 4. The 24 hours — what to actually watch

The silent failure is an empty list, so count rows, don't tail for exceptions.

**The loud half**, which is cheap to catch:

```bash
docker compose logs --no-color api worker \
  | grep -Ei "row-level security|permission denied for table|invalid input syntax for type integer"
```

The third pattern is there on purpose: a GUC that was set and then `RESET` comes back as `''`, not NULL, and
`''::int` raises. The predicate uses `nullif(…, '')` for exactly this, so a hit here means something is setting
the context in a way the code does not.

**The silent half.** Pick one real tenant with a known, non-trivial amount of data and compare what the owner sees
against what `app_rw` sees with the context set. They must be equal:

```sql
-- as the owner, while FORCE is off:
SELECT count(*) FROM bookings WHERE tenant_id = 1;

-- as app_rw. Session-level SET, not SET LOCAL: outside a transaction block
-- SET LOCAL only warns and changes nothing, which would make this check pass
-- for the wrong reason. The app itself sets it transaction-locally.
SET app.tenant_id = '1';
SELECT count(*) FROM bookings;   -- must equal the number above
RESET app.tenant_id;
SELECT count(*) FROM bookings;   -- must be 0 — this is the fail-closed proof
```

Repeat for the tables a user would notice within a day: `bookings`, `documents`, `bank_transactions`, `matches`,
`kontenplan`, `memory`, `review_queue_items`. Seven counts, twice a day, is a ten-minute job and it is the only
check that sees the failure this whole exercise is about.

**The one that needs a human.** Sign in as a real user and load Heute, Belege, Bank and Kontenplan. An endpoint
that lost its context renders as a working page with nothing on it, and no log line anywhere says so.

---

## 5. Rollback

In increasing order of severity. The first two are seconds.

1. **An operator lost visibility, or a read-only tool broke:** `FORCE` is already off during the watch; connect
   as the owner. Nothing to undo.
2. **The application is returning empty lists:** point `DATABASE_URL` back at the owner role and restart.
   *Caveat:* in production the app refuses to boot as a superuser. If `POSTGRES_USER` is a superuser — it is, in
   the compose image — this rollback needs a second NOSUPERUSER role that is also `BYPASSRLS`, or the migration
   reversed. **Create that role before step 3, not during an incident.**
3. **Reverse the migration:** `alembic downgrade -1` as the owner. It drops the policies and disables RLS on all
   24 tables. Data is untouched — no row is written or deleted by either direction.

What is **not** reversible: nothing here. That is the one genuinely reassuring property of this change — it is
entirely a permissions change. Which is also why a restore from backup should never be needed, and why step 2's
missing fallback role is the only real trap in the list.

---

## 6. Done means

- [ ] 24 h elapsed with the counts in section 4 equal, every time they were taken.
- [ ] No `row-level security` or `permission denied` line in the API or worker logs.
- [ ] `FORCE` back on for all 24 tables, verified with query (b).
- [ ] The app runs as `app_rw`, verified with query (c).
- [ ] ADR-002 action item 8 ticked, with the date and what was seen.
