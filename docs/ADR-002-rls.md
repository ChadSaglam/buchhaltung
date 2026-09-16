# ADR-002: Postgres Row-Level Security as defence in depth (B-24)

**Status:** Accepted and implemented (2026-09-16)
**Date:** 2026-09-12
**Deciders:** Chad (owner)
**Related:** ADR-001 (platform auth contract, chadev-platform), B-24, B-40 (role ladder), B-41 (prod compose)

## Context

Tenant isolation is enforced in exactly one layer today: every query adds `.where(tenant_id == user.tenant_id)`
with the id taken from `get_current_user` (`core/deps.py:14-44`). The 2026-09-12 review confirmed this is applied
consistently across all 17 routers and is covered by `test_tenant_isolation.py` (30+ routes). It also found that the
*next* class of mistake is not a missing `.where` but a missing `Depends` (`require_editor` exists and is used
nowhere — B-40). A single forgotten filter on a new endpoint, a raw `text()` query, a psql session by an operator, or a
future reporting job would expose one tenant's bookkeeping to another. Swiss bookkeeping data is the product; a
cross-tenant leak is an existential incident, not a bug.

Forces in play:

- **Session plumbing.** One engine, one `async_session` factory (`core/database.py:15-17`); `get_db` yields one
  session per request and commits at the end (`:20-27`). But 27 call sites commit or roll back *mid-request*
  (`classify.py` ×8, `review.py:77,99`, `kontenplan.py:51`, `scanner_service.py:79,84,107`, `import_data.py:244`,
  `sso.py:38,40`, `platform_events.py:61,63`, …). Anything transaction-scoped (`SET LOCAL`) is lost after each one.
- **The tenant is known late.** `get_current_user` first selects `users` by id, then `tenants` (`deps.py:29,40`) —
  before any tenant context exists. `register`/`sso` create tenant + user + Kontenplan rows before a context could be
  set (`tenant_setup.py:75-87`); SSO's email-collision guard is a cross-tenant read *by design* (`sso.py:210-213`).
- **Three paths with no user.** Platform events resolve the tenant from the HMAC-verified payload
  (`platform_events.py:131-136`); the training worker claims jobs across all tenants
  (`training_worker.py:62-81`) and only then knows `job.tenant_id`; the health probe touches `alembic_version` only.
- **Roles.** Alembic and the app share `DATABASE_URL`; in compose that user is the container superuser. Postgres
  silently bypasses RLS for superusers and table owners unless `FORCE ROW LEVEL SECURITY` is set and the app connects as
  a non-owner. `AUTO_CREATE_TABLES` (dev) creates tables as the connecting role, which then owns them.
- **Pooling.** asyncpg connections are reused; a session-level `SET` survives SQLAlchemy's reset-on-return
  (`ROLLBACK` does not clear GUCs) and would leak the previous tenant into the next checkout.
- **Tests.** Local `make check` runs on SQLite (no RLS); CI runs on Postgres. Policies can only be proven on PG.
- **Cost of doing nothing.** Zero today. The app layer is correct. The value of RLS is entirely in the failure case.

## Decision

Adopt **Option A — RLS on the 12 tenant-scoped tables with `SET LOCAL app.tenant_id` re-issued on every transaction
begin, plus the migrator/app role split from Option C.** Keep the application-level filter as the primary mechanism;
RLS is the backstop that fails *closed* (0 rows) when the context is missing.

Do this **after** B-39/B-40/B-41 (prod-blocking fixes) and before the first paying tenant.

## Options considered

### Option A: RLS + `SET LOCAL` via a SQLAlchemy `after_begin` listener

A `ContextVar[int | None]` in `core/tenant_context.py`; an `after_begin` event on the sync session class issues
`SET LOCAL app.tenant_id = :tid` at the start of *every* transaction (skipped on SQLite). Context is set in four places:
`get_current_user` after `deps.py:43`, `TrainingWorker._run` from `job.tenant_id` (`training_worker.py:85-89`),
`receive_event` after `resolve_tenant` (`platform_events.py:99`), `sso_login` after `mirror_tenant` (`sso.py:35`).
Alembic runs as the table owner via a new `MIGRATION_DATABASE_URL`; the API/worker connect as `NOSUPERUSER NOBYPASSRLS`.

| Dimension | Assessment |
|---|---|
| Complexity | Medium — ~150 lines (listener, contextvar, 4 call sites, 1 migration, 1 setting) + role setup |
| Cost | One `SET LOCAL` round-trip per transaction (~0.1 ms local); ops: two DB users |
| Scalability | Unaffected; compatible with transaction-mode pgbouncer (session `SET` would not be) |
| Team familiarity | Chad has done Alembic + savepoints already; RLS policies are new |

**Pros:** covers every SQL path including raw `text()`, psql, future bugs; fails closed; survives the 27 mid-request
commits because the GUC is re-issued on every `begin`; no change to router code.
**Cons:** PG-only proof (SQLite suite cannot exercise it); worthless without the role split — a misconfigured deploy
(app as owner) silently disables it, so the test must assert `rolbypassrls = false` for the connected role; the
context-missing case turns into "empty list" rather than an error unless a `RAISE` policy is used for writes.

### Option B: Application guard only + global ORM filter (`with_loader_criteria` in `do_orm_execute`)

| Dimension | Assessment |
|---|---|
| Complexity | Low — one event listener, DB-agnostic |
| Cost | None |
| Scalability | Unaffected |
| Team familiarity | High |

**Pros:** cheapest; runs in the SQLite suite too; catches a forgotten `.where` on ORM `select()`.
**Cons:** not defence in depth — it lives in the same layer as the bug it guards; does not cover `text()`, `INSERT`
with a wrong `tenant_id`, `func.sum` core selects, psql, or a leaked session. Good *additional* net, not a decision.

### Option C: RLS + one DB role per process (api / worker / migrator)

| Dimension | Assessment |
|---|---|
| Complexity | High — three users, compose init SQL, `BYPASSRLS` for the worker's cross-tenant claim |
| Cost | More secrets to manage; every env (dev, e2e, CI, prod) needs the role set |
| Scalability | Enables least privilege per process later |
| Team familiarity | Low |

**Pros:** least privilege; the worker can claim jobs cross-tenant without a policy exemption.
**Cons:** `RUN_WORKER_IN_API=true` (current default) makes the worker share the API connection — a `BYPASSRLS`
worker role would then be on every request connection, defeating the point. Premature with one worker type.

## Trade-off analysis

- **A vs B:** B is not a backstop, it is the same guard written twice. Only A stops a query the ORM never saw.
- **A vs C:** C's extra roles buy nothing until the worker is a separate process by default and there is more than one
  worker type. Take C's *migrator ≠ app role* split now (mandatory for RLS to be real), defer the rest.
- **`SET LOCAL` on `after_begin` vs `SET` on checkout:** `SET` leaks across pooled connections and breaks
  pgbouncer transaction mode; `SET LOCAL` on every begin is the only variant that is correct with the mid-request commits.
- **Global tables.** `tenants`, `users`, `sso_nonces`, `training_jobs`, `alembic_version` stay without policies:
  they are read before a tenant is known or across tenants by design. `users` gets no policy — the takeover guard and
  `/login` by email need global reads; app-level filtering stays the guard there.
- **Fail-closed semantics.** `current_setting('app.tenant_id', true)` returns NULL when unset → `NULL = tenant_id`
  is never true → SELECT returns 0 rows, INSERT/UPDATE are rejected by `WITH CHECK`. A missed context site shows up as
  an empty page, which is the safe failure. Log a warning from the listener when the contextvar is `None` on PG so it is
  visible.

## Consequences

- Easier: proving isolation to a Treuhänder/auditor ("the database refuses cross-tenant rows"); adding endpoints —
  a forgotten filter degrades to an empty result instead of a leak; operator psql sessions are safe by default.
- Harder: every new code path that opens a session must set the context (4 today; add a lint/grep test for
  `async_session()` call sites); dev bootstrap needs two DB users (`scripts/setup.sh`, compose `db` init SQL);
  the SQLite suite cannot cover RLS — CI's PG job becomes the only proof (make the PG matrix part of `make check`
  when PG is reachable, B-60).
- Revisit: per-service roles (Option C) once the worker is separate by default; a `RAISE`-ing write policy if
  silent empty results prove confusing; `users` policy if per-tenant admin tooling arrives.

## Action items

1. [x] Land B-39, B-40, B-41 first (prod blockers).
2. [x] `core/tenant_context.py` (`ContextVar`) + `after_begin` listener in `core/database.py`, PG-only.
3. [x] Set the context at the four sites: `deps.py` (`get_current_user`), `training_worker._run`,
       `platform_events.receive_event`, `sso.sso_login`.
4. [x] Migration `f1a2b3c4d5e6_enable_rls`, over the list in `core/rls.py` (24 tables, not the 12 the
       2026-09-12 draft named — the schema grew; see below).
5. [x] Settings: `MIGRATION_DATABASE_URL`; production refuses an empty value, refuses equality with
       `DATABASE_URL`, and `verify_rls_role()` refuses to boot as `rolsuper` or `rolbypassrls`.
6. [x] `migrate-and-run.sh` uses `MIGRATION_DATABASE_URL`; `docker/db-init/10-app-role.sql` creates
       `app_rw NOSUPERUSER NOBYPASSRLS` with DML grants and default privileges.
7. [x] `tests/test_rls.py` — 10 PG-only tests plus 10 that run everywhere.
8. [ ] Canary: deploy one replica, watch for empty-list regressions for 24 h, then flip all.

## What implementation changed about the plan

**The table list grew from 12 to 24, so it is no longer written down only in the migration.** The 2026-09-12 draft
named the tables that existed then; `documents`, `invoice_positions`, `company_profiles`, `bank_transactions`,
`matches`, `export_batches`, `email_messages`, `mail_settings`, `idempotency_keys` and the three Lohn tables have
arrived since. A list inside one migration is a list nobody reads again, so it lives in `app/core/rls.py` and
`test_rls.py` holds it against the models: a table that grows a `tenant_id` and is neither covered nor exempt fails
the suite. That test is the only thing that keeps this true in a year.

**The policy predicate needed a `nullif`.** `current_setting('app.tenant_id', true)` returns NULL when the GUC was
never set — but a GUC that was set and then `RESET` comes back as the **empty string**, and `''::int` raises
`invalid input syntax for type integer`. That is a 500 where an empty list belongs, so the predicate is
`tenant_id = nullif(current_setting('app.tenant_id', true), '')::int`. Found by running it, not by reading it.

**`bind_tenant` had to be added next to the listener.** `get_current_user` reads `users` and `tenants` before it
knows the tenant, which opens the request's first transaction — so `after_begin` has already fired by the time the
context exists. Without an explicit `set_config` on that open transaction, the first transaction of every request,
the one that goes on to do the work, would run unscoped. The listener covers every transaction after it.

**The role split is not optional, and that is now demonstrable.** Applied against a real Postgres while connected as
the bootstrap superuser, the policies were in place, `FORCE ROW LEVEL SECURITY` was set, and tenant 1 could still
read tenant 2's bookings and insert rows into tenant 2 — because Postgres exempts a superuser from every policy and
nothing overrides that. The same database, connected as `NOSUPERUSER NOBYPASSRLS`, returns 1 row and rejects the
insert. This is the failure mode worth fearing: it looks enabled, it looks correct, and it does nothing. Hence
`verify_rls_role()` refusing to boot in production, and the test asserting `rolbypassrls OR rolsuper` is false before
any of the others mean anything.

**Backups connect as the owner on purpose.** A `pg_dump` as `app_rw` with no `app.tenant_id` set would contain zero
rows from all 24 tables and exit 0. `scripts/backup.sh` uses `POSTGRES_USER`, and the manifest's row counts (B-25)
would catch it if that ever changed.
