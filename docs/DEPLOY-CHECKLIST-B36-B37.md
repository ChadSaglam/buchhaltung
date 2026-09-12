# Deploy checklist — release `9e0c22b` (B-36 SSO + B-37 platform events)

**Date:** 2026-09-12 · **Deployer:** Chad · **Migration:** `a400bdc46480` (additive) · **Rollback unit:** the image, not the migration

> Status 2026-09-12: **NOT READY.** Three blockers from the deep review must land first (section 0).
> Everything else below is verified against the code at `9e0c22b` (file:line in brackets).

## 0. Blockers — do before the rest of this list

- [ ] **B-39** `training_data` migration exists and `alembic upgrade head` on a fresh PG creates it
      (`ENVIRONMENT=production` disables `create_all` → import + training would 500 today).
- [ ] **B-41** Production compose: `ENVIRONMENT=production` on `api` **and** `worker`; `SECRET_KEY=${SECRET_KEY:?}`;
      no `--reload` (`backend/Dockerfile:20`); worker runs `python -m app.worker` **without** the migrate ENTRYPOINT
      (or a one-shot `migrate` service + `service_completed_successfully`); no `ports:` on db/redis/ollama;
      `backend/.dockerignore` (`venv .env* tests *.db`); `USER app`.
- [ ] **B-40** role ladder wired (a `viewer` from SSO must not be able to mutate) — SSO makes viewer accounts real for the first time.

## 1. Pre-deploy

- [ ] CI green on `main` for the exact commit (backend PG job, migrations up/down job, frontend lint+tsc+vitest+e2e, security.yml).
- [ ] `make check` green on the Mac; `STATUS.md` regenerated (`make status`) and committed.
- [ ] `git log ecc48b9..HEAD` reviewed: `9e0c22b` only touches the e2e build env.
- [ ] Env, backend (`core/config.py`):
  - [ ] `PLATFORM_SHARED_SECRET` [config.py:95] — same bytes as billing's; **not** derived from `JWT_SECRET`; ≥ 32 chars. Unset → `/api/auth/sso` and `/api/platform/events` answer **404** [sso.py:29-31, platform_events.py:42-44] — that is the "feature off" switch.
  - [ ] `SECRET_KEY` ≥ 32 chars, not in `INSECURE_SECRETS` [config.py:11,140] (prod refuses to boot otherwise — good).
  - [ ] `CORS_ORIGINS` includes the frontend origin serving `/sso` [config.py, main.py].
  - [ ] `BILLING_URL` [config.py:97] is read by nothing — optional; do not spend time on it.
  - [ ] `SMTP_PORT`: compose injects 587, config default 465 → decide one (587 = STARTTLS path) [config.py:67, docker-compose.yml].
- [ ] Env, frontend: `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_BILLING_URL` are **build-time** [frontend/src/lib/platform.ts:8-10]. Pass them as `build.args`/`ARG` (B-62) — a runtime `environment:` entry does nothing; the Apps switcher stays hidden and the API URL falls back to `localhost:8000`.
- [ ] Migration `a400bdc46480` [alembic/versions/a400bdc46480_*.py:29-45] reviewed: creates `sso_nonces(jti PK, expires_at)`; adds `tenants.platform_tenant_id` (nullable, unique), `users.platform_user_id` (nullable), `users.auth_source NOT NULL DEFAULT 'local'`, unique `(tenant_id, platform_user_id)`. **Additive with server defaults → old image keeps working during rollout.** Downgrade exercised in CI (`test_tenant_migration_is_reversible`).
- [ ] Backup taken **before** migrating: `pg_dump -Fc` of the DB and a copy of the `model_data` volume (receipts + model blobs). There is no scheduled backup yet (B-25) — do it by hand and record where it went.
- [ ] Rollback plan agreed (section 5). On-call = Chad; billing side informed of the deploy window.

## 2. Ordering with billing

1. **buchhaltung first.** `/sso` 404s harmlessly until billing links to `/sso#token=…`.
2. Billing enables the SSO link → **at least one SSO hop per tenant** (creates `tenants.platform_tenant_id`).
3. Only then billing starts sending `invoice.paid`: `resolve_tenant` answers **404 `unknown_tenant`** for a tenant that never did SSO, and billing treats 404 as final (no retry) [platform_events.py:131-136]. Sending before step 2 silently drops payments.

## 3. Deploy

- [ ] Staging: run the migration + image, execute the smoke tests below, do one real SSO hop from staging billing.
- [ ] Production: migrate (one process only — see B-41), roll the API, then the worker, then the frontend.
- [ ] Smoke tests (paths/headers from the routers):
```bash
curl -s -i https://API/api/health                     # 200 {"status":"ok","version":"2.0.0"} (prod trims the body)
curl -s -i -X POST https://API/api/auth/sso -H 'Content-Type: application/json' -d '{"token":"garbage"}'
#   401 {"error":{"code":"sso_invalid"}}   ← 404 http_404 means PLATFORM_SHARED_SECRET is unset
curl -s -i -X POST https://API/api/platform/events -H 'Content-Type: application/json' \
  -H "X-Platform-Timestamp: $(date +%s)" -H 'X-Platform-Signature: sha256=deadbeef' -d '{}'
#   401 {"error":{"code":"bad_signature","message":"Signatur ungültig"}}
curl -s -i -X POST https://API/api/platform/events -H 'X-Platform-Timestamp: 1000' \
  -H 'X-Platform-Signature: sha256=00' -d '{}'         # 401 stale_timestamp
```
- [ ] Positive path: sign `"<ts>.<body>"` with the real secret for a known `tid` [platform_events.py:51-54] → **202** `accepted`; send it again → **200** `duplicate`. Verify exactly one booking `1020 Bank an 1100 Debitoren`, `source=billing`, `rechnung=<number>`, amount half-up to 2 decimals.
- [ ] Real SSO hop from billing: lands on `/dashboard`, `users.auth_source='platform'`, `password_hash='!platform'`; `/login` with that email → **403 `platform_user`** [auth.py:71-72].
- [ ] Watch for 15 min: 5xx rate, p50 latency on `/api/auth/sso` and `/api/platform/events`, worker log (`training_jobs` claimed/finished).

## 4. Post-deploy (24 h)

- [ ] Codes per `request_id`: `sso_invalid`, `sso_expired`, `sso_replayed`, `email_taken_locally`, `bad_signature`, `stale_timestamp`, `unknown_tenant`, `unsupported_*` — all should be ~0 in steady state.
- [ ] Ratio 202/200 on `/api/platform/events` mostly 202; bookings with `source='billing'` per tenant == billing's paid invoices for the day (reconcile `source_key LIKE 'billing:invoice:%'`).
- [ ] 429s on `/api/auth/sso` and `/api/platform/events`: behind a proxy every anonymous request keys as `ip:<proxy>` and shares one 200/min bucket (no `--forwarded-allow-ips`, B-55) — a login burst would starve billing's sender.
- [ ] `sso_nonces` row count stays small (purged on each hop; no index on `expires_at` — fine at this volume).
- [ ] `training_jobs` rows in `running` > 15 min → stuck worker (B-57).
- [ ] Update `STATUS.md`, ROADMAP "Done", SESSION-HANDOFF; tell billing the tenant mapping is live.

## 5. Rollback triggers and procedure

| Signal | Meaning | Action |
|---|---|---|
| `sso_invalid` on every hop | secret mismatch or wrong `iss`/`aud`/`type` [sso.py:86-106] | fix env, redeploy config — not a code rollback |
| `sso_expired` / `stale_timestamp` spikes | clock skew (token TTL ≤ 120 s, events ±300 s) | fix NTP on both hosts first |
| `sso_replayed` from real users | `/sso` posting twice or billing reusing `jti` | check frontend build (StrictMode guard is in `app/sso/page.tsx`) |
| `email_taken_locally` (409) in bulk | billing's tenant mapping wrong | pause the billing link |
| `unknown_tenant` for tenants that did SSO | `platform_tenant_id` mismatch | stop billing's sender, inspect `tenants` |
| `internal_error` on `/api/platform/events` | duplicates possible (SELECT-then-INSERT, B-52) | reconcile bookings by `source_key` |
| 5xx > 1 % or p50 > 500 ms for 10 min | regression | **roll back the image only** |

**Never downgrade `a400bdc46480` once any SSO hop happened**: shadow users keep `password_hash='!platform'` and the old
image reaches `bcrypt.checkpw` with a non-bcrypt hash → 500 on `/login` [auth.py:73]. The migration is additive; the old
image runs fine on the new schema.

Open question to decide before go-live: `receive_event` does not check `tenant.is_active` — a deactivated tenant still
receives bookings from billing. Intended?
