# ROADMAP — Buchhaltung (ChaDev Platform · product 2 of 2)

> One running list. Never duplicated — items move between sections, they don't get re-added.
> Legend: severity `C`ritical / `H`igh / `M`edium / `L`ow · effort `S` (<1h) / `M` (half day) / `L` (multi-day)
> IDs: `B-xx` = work item (next free: **B-39**) · `P-xx` = parked (next free: **P-05**)
> Cross-product items (SSO, contracts, design tokens) live in `chadev-platform/ROADMAP.md`, not here.
> Updated: 2026-09-11

---

## 🎯 North star — what "done" looks like

| Owner's words | What it means in this repo | Tracks that deliver it |
|---|---|---|
| **more dynamic** | Scan → classify → book without a reload; live review queue; optimistic booking edits | B-14, B-15, B-16 |
| **more professional** | Money that rounds right in every export, audit trail, branded Steuerberater hand-off | B-01 ✅, B-04 ✅, B-05 ✅, B-09 ✅, B-17 |
| **easier to improve** | No god-files, one type source, tests that catch regressions, jobs outside the API process | B-02 ✅, B-03 ✅, B-08 ✅, B-10 ✅, B-11 ✅, B-13 ✅, B-33 ✅ |
| **together** (platform) | One login across billing + buchhaltung, paid invoices book themselves | B-36 ✅, B-37 ✅, B-38 🅿️ |
| **more user-friendly** | Loading/empty/error states everywhere, keyboard-first review, a11y, onboarding | B-18 ✅, B-19 ✅, B-20, B-21 |

Rule: every PR names the B-ID it closes and which north-star column it serves.

---

## 🔥 NOW — do these in order (one at a time)

- [ ] **B-14** Review queue: optimistic accept/reject with rollback; keyboard `j/k/a/r`. (Queue is on SWR since
      B-18 — `mutate(optimistic, { rollbackOnError: true })` is the whole change.) — `M` / `M`
- [ ] **B-16** Dashboard KPIs auto-refresh (SWR `refreshInterval`), no reload. — `L` / `S`
- [ ] **B-21** Replace remaining `err: any` in scanner/modell hooks with generated types (5 eslint warnings). — `L` / `S`

---

## ⏭ NEXT — "easier to improve" foundation

- [ ] **B-15** Scan progress streamed (NDJSON already used by AI chat) instead of spinner. — `M` / `M`
- [ ] **B-34** `classifier_models.model_sha256` column: record the digest of the packed model at training
      time and check it in `model_blob.unpack()` on top of the HMAC (detects silent corruption, lets an
      operator audit which model is live). Also: a "Modell neu trainieren" hint in the UI when the API
      logs an unsigned blob. — `L` / `S`

---

## 📋 LATER — by track

### Professional
- [ ] **B-17** Steuerberater export pack: Banana TSV + PDF summary + receipts zip, one click. — `M` / `L`
- [ ] **B-22** Audit log surfaced in UI (model exists: `audit_log.py`). — `M` / `M`
- [ ] **B-23** Usage limits enforced from `usage_event` (plan free/pro). — `M` / `M`

### User-friendly
- [ ] **B-20** Onboarding: first scan guided, sample receipt, Kontenplan import wizard. — `M` / `M`

### Security & data
- [ ] **B-24** Postgres RLS (`SET LOCAL app.tenant_id`) as defence in depth — after platform contract. — `H` / `L`
- [ ] **B-25** Backup/restore script + restore drill (models + DB). — `H` / `M`

### Performance
- [ ] **B-27** N+1 audit on bookings list + stats. — `M` / `M`
- [ ] **B-28** Index audit: `(tenant_id, date)`, `(tenant_id, status)` on bookings. — `M` / `S`

---

## 🅿️ Parked
- **P-01** Abacus export format (client request).
- **P-02** Client portal for buchhaltung (Steuerberater view).
- **P-03** Mobile PWA for receipt capture.
- **P-04** Stripe vs Lemon Squeezy — decided at platform level (chadev-platform 6.4).
- **B-38** `invoice.unpaid` reversal event (status set back from `paid` in billing → storno of the B-37 booking).
  Not in events v1 (contracts/events.md); needs a decision on storno vs. delete first.

---

## ✅ Done

- **B-30** ✅ 2026-09-11 — `scripts/status.sh` → `STATUS.md` (`make status`): app version, backend/vitest/e2e test
  counts, routers + routes, models, Alembic migrations + head (venv `alembic heads`, else derived from the files),
  open B-xx table folded from ROADMAP.md, done count, date + commit. Pure grep/find, shellcheck-clean;
  `scripts/project-overview.sh` untouched.
- **B-29** ✅ 2026-09-11 — Pre-commit gates completed: `api-types` local hook at pre-push runs
  `scripts/gen-api-types.sh` and fails on `git diff` of `frontend/src/lib/api-types.ts` (same check as the CI
  "api-types" job), triggered by `backend/app/{routers,schemas,models}/**.py`; `eslint` (`npm run lint`) at pre-push
  for `frontend/**.{ts,tsx,css}` — the frontend has no prettier, so eslint is the formatter gate. ruff, gitleaks,
  tsc were already in place.
- **B-37** ✅ 2026-09-11 — Inbound platform events (contracts/events.md, receiver side). `POST /api/platform/events`
  (`routers/platform_events.py`, `services/platform_events.py`): HMAC-SHA256 over `"<ts>.<raw body>"` from
  `X-Platform-Signature: sha256=<hex>` with `PLATFORM_SHARED_SECRET` (constant-time), `X-Platform-Timestamp` ±5 min;
  no Bearer, default per-IP rate limit. `invoice.paid` v1 → one booking `1020 Bank an 1100 Debitoren`, amount from
  the decimal string via `round_chf` (half-up), `datum` = `paid_at` as `DD.MM.YYYY`, text `Zahlung <number> <client>`,
  `source=billing`, `rechnung=<number>`, idempotent on `source_key=billing:invoice:<id>:paid` (202 accepted / 200
  duplicate). 404 secret unset · 401 `bad_signature`/`stale_timestamp` · 400 `unsupported_version`/`unsupported_event`/
  `invalid_payload` · 404 `unknown_tenant` (tid never did SSO — final for billing). `core/errors.py` gained
  `ApiError(status, code, message)` so a route can name its envelope code. 13 tests, signed like billing's sender.
- **B-36** ✅ 2026-09-11 — SSO hand-off + tenant mirroring (contracts/sso.md, ADR-001 amendment, verifier side).
  `POST /api/auth/sso {token}` (`routers/sso.py`, `services/sso.py`): HS256 with `PLATFORM_SHARED_SECRET`,
  `iss=billing`/`aud=buchhaltung`/`type=sso`, `exp-iat ≤ 120 s`, `jti` single-use via `sso_nonces` table (works across
  workers, expired rows purged on the way). 404 secret unset · 401 `sso_invalid`/`sso_expired`/`sso_replayed` · 409
  `email_taken_locally`. Migration `a400bdc46480` (batch ops, PG + SQLite): `tenants.platform_tenant_id` (unique),
  `users.platform_user_id` + `auth_source` (default `local`), unique `(tenant_id, platform_user_id)`, `sso_nonces`.
  First hop creates the tenant from the snapshot (`unique_tenant_slug` + `seed_tenant`) and a shadow user
  (`auth_source=platform`, `password_hash="!platform"`); later hops refresh tenant name/plan/trial and user
  email/name/role. `/api/auth/login` answers 403 `platform_user` for shadow users before checking the password.
  Roles pass through on the shared ladder (unknown → viewer; billing `admin` stays `admin`, no promotion to owner).
  Same email as a local user of the same mirrored tenant → linked (keeps password/role); other tenant → 409.
  Frontend: `/sso` reads `#token=` once (StrictMode-safe), clears the fragment, stores the session like `/login`,
  `router.replace("/dashboard")`, translated error state with a link to `/login`; "Apps" switcher in the top bar
  (`AppSwitcher`, `lib/platform.ts`) links to `NEXT_PUBLIC_BILLING_URL`, hidden when unset. Env: `PLATFORM_SHARED_SECRET`,
  `BILLING_URL`, `NEXT_PUBLIC_BILLING_URL` (.env examples, compose, README "Platform (SSO + events)"). Tests: 18 pytest
  (PG 339 / SQLite 335 passed), Playwright 14 → **17** (`e2e/sso.spec.ts` mints the token with node:crypto).
- **B-19** ✅ 2026-09-11 — a11y pass. Skip link → `<main id="main">` (AppShell, login, register); `hooks/useFocusTrap`
  gives CommandPalette, ShortcutsModal, AssistantPanel and the mobile sidebar Tab-cycling, `Esc` and focus return;
  `<html lang>` follows `getLocale()` (`LangSync`, `setLocale`); every input/select/textarea has a label
  (settings, scanner InvoiceCard `Field` is now a `<label>`, dropzone file inputs, search fields), every table an
  `aria-label`, decorative icons `aria-hidden`. Contrast: light `--muted-foreground`/`--success`/`--warning` are the
  platform tokens mixed 15 % toward `--cd-color-fg` (raw values were 4.1–4.3:1 on the app's tinted chips), `--link`
  = `--cd-color-brand-hover` in dark (brand is 4.2:1 as text), opacity-faded text removed. Found on the way:
  `dark:` utilities never applied — Tailwind 4 defaults to `prefers-color-scheme`, the app toggles `.dark`; fixed
  with `@custom-variant dark`. Gate: `e2e/a11y.spec.ts` (`@axe-core/playwright`) fails on any serious/critical
  violation on login, dashboard, scanner, modell, settings in light **and** dark, plus skip-link and focus-trap
  checks. Playwright 3 → **11**. Advisory (moderate) left open: heading-order on `modell`, duplicate landmark on
  `settings`.
- **B-18** ✅ 2026-09-11 — Every dashboard page has skeleton / empty / error. Shared `components/shared/`
  `EmptyState` (existing) · `ErrorState` (envelope `error.message` + request id via `lib/errors.ts`, retry =
  SWR `mutate` or the hook's `load`) · `PageSkeleton` (header/metrics/rows; `dashboard/loading.tsx` uses it).
  Copy is in `lib/i18n.ts` (DE + EN; FR falls back to DE). `review`, `audit`, `kontenplan`, `lernverlauf` moved
  to SWR so retry is a `mutate()`; `kontenplan`, `lernverlauf`, `kontoauszug`, `scanner` split into
  `hooks/ components/ types.ts` (B-10 rule, every page ≤ 120 lines). `alert()` is gone. vitest 58 → **65**
  (`states.test.tsx`, jsdom for the three components only).

  | Page | Before (loading · empty · error) | After |
  |---|---|---|
  | `dashboard` | metric skeletons · `GettingStarted` · none — cards showed "–" | skeletons · same · inline `ErrorState`, retry re-fetches both keys |
  | `review` | "Laden…" spinner · `EmptyState` without action · swallowed (looked empty) | `PageSkeleton` · `EmptyState` + "Rechnung scannen" · `ErrorState` + `mutate`; approve/reject failures toast the envelope |
  | `audit` | one `MetricCardSkeleton` · `EmptyState` · red sentence, no retry | `PageSkeleton` · `EmptyState` + action · `ErrorState` + `mutate`; table has `aria-label` |
  | `kontenplan` | none · none (blank table) · none (unhandled rejection) | `PageSkeleton` · `EmptyState` (+ "Keine Konten gefunden" for a filtered list) · `ErrorState` + retry; save/train report the envelope |
  | `lernverlauf` | whole page spinner · per-tab `EmptyState` (charts: none) · none (unhandled rejection) | `PageSkeleton` · translated `EmptyState` per tab + action, charts included · `ErrorState` + retry |
  | `kontoauszug` | processing card · drop zone · `alert()` with raw `detail` | same · drop zone (keyboard-operable) · `ErrorState` with "Erneut versuchen" (same file) or "Andere Datei"; save/export failures toast the envelope |
  | `scanner` | `StatusBar` skeleton · `DropZone` · toast only | same · same · inline `ErrorState` per failed file with retry; envelope message instead of raw `detail` |
  | `modell` | spinner · none (only the status badge) · toast, then a blank page | `PageSkeleton` · `EmptyState` "Noch kein Modell trainiert" + train action · `ErrorState` + retry |
  | `insights` | spinner in `ResultsTable` · "Keine Treffer" (search only) · none (silently empty) | `PageSkeleton` · `EmptyState` "Noch keine Buchungen" + "Kontoauszug hochladen" · `ErrorState` + retry |
  | `settings` | none ("–" placeholders) · n/a · swallowed | `PageSkeleton` in the tab body · n/a · `ErrorState` + retry; save failures toast |
- **B-35** ✅ 2026-09-10 — Scanner-config first-call race: the dashboard fires several `/api/scanner/*` calls at
  once and every one tried to insert the tenant's `scanner_configs` row. `get_or_create` now tolerates the lost
  `IntegrityError` and re-reads the winner (83bb0b2, `ScannerService`), and the review-threshold service wraps its
  insert in a savepoint so a lost race cannot poison the request session (c1c2b01, `services/scanner_config.py`).
  Both paths regression-tested in `test_scanner_pipeline.py`.
- **B-13** ✅ 2026-09-10 — `GET /api/health` → `{status, version, database, migration_head, storage, worker}`:
  `database` ok/error (status `degraded` on error), `migration_head` = revision applied in the DB (null on a
  create_all schema), `storage` = backend name, `worker` = `in-api` | `separate`. `ENVIRONMENT=production` trims
  the body to `status` + `version`. Tests 303 → **307** (PG).
- **B-10** ✅ 2026-09-10 — `settings/page.tsx` 352 → 66 and `insights/page.tsx` 320 → 53 lines, split into
  `hooks/ components/ helpers.ts types.ts` like `modell/`; largest new file 82 lines. No markup or copy change;
  the e2e Insights step still finds the search input and table.
- **B-09** ✅ 2026-09-10 — Every upload to `/api/scanner/extract` and `/api/pdf/parse` is written through
  `services/storage.py` as `receipts/<tenant_id>/<uuid>.<ext>` *before* extraction (`services/receipts.py`) and
  returned as `source_key`. Migration `55e64308d75f` adds nullable `bookings.source_key`; `POST /api/bookings/`
  accepts it only for the caller's own tenant (400), `GET /api/bookings/{id}/source` streams the file (404
  cross-tenant, keyless, or vanished — isolation suite). Kontoauszug passes the key through on save. Tests run
  LocalStorage under `tmp_path` (autouse fixture). Tests 290 → **303** (PG).
- **B-08** ✅ 2026-09-10 — `python -m app.worker` is a real entrypoint (loops, `--once`); the API lifespan starts
  the same jobs in-process only with `RUN_WORKER_IN_API=true` (default). The training queue moved from process
  memory to `training_jobs` (migration `52eb7a4363f0`): `log_correction` enqueues in the request session, the
  worker claims by conditional update, dedups per tenant, hands a job back on shutdown. Compose: `worker` service
  (same image, restart unless-stopped, waits for the api healthcheck), api runs `RUN_WORKER_IN_API=false`.
  Found on the way: the B-04 migration test used `downgrade -1`, which broke as soon as a newer migration
  existed — now targets its base revision. Tests 282 → **290** (PG; 279 → 287 SQLite).
- **B-33** ✅ 2026-09-10 — Playwright happy path against the real API: `playwright.config.ts` starts uvicorn on
  8100 with a throw-away SQLite DB + the frontend with `NEXT_PUBLIC_API_URL`; `e2e/happy-path.spec.ts` registers,
  opens Kontenplan, books via the API with the UI's token, finds the row in Insights, exports CSV. CI frontend job
  installs the backend for the server. Note: there is no manual booking form in the UI.
- **B-11** ✅ 2026-09-10 — vitest (`npm run test`, in CI and `make test`): 58 tests for `lib/errors.ts`,
  `modell/helpers.ts`, `lib/booking-analytics.ts`. Pure helpers only; pages stay on Playwright.
- **B-32** ✅ 2026-09-10 — bandit `-ll` blocking. `defusedxml` for uploaded Banana XML; every Ollama `httpx` call has
  a settings timeout (`OLLAMA_TIMEOUT` 60 s, `OLLAMA_VISION_TIMEOUT` 120 s, `OLLAMA_PROBE_TIMEOUT` 10 s). Found on the
  way: `POST /api/classify/upload` stored any `.pkl` that `_load_model()` later unpickled (RCE for a logged-in user).
  Model blobs are now HMAC-SHA256 signed with `SECRET_KEY` (`services/model_blob.py`); unsigned blobs are rejected on
  upload and ignored on load (retrain once). No schema change; sha256 column → B-34. Tests 253 → **277** (SQLite).
- **B-04** ✅ 2026-09-10 — `preprocess()` strips month tokens as whole words (`\b`, optional trailing dot; `"mr"` →
  `"mär|mrz"`). Data migration `4c7e2a91b0d3` re-derives every `memory.lookup_key` (source text recovered from the
  tenant's latest matching `corrections` row, else the new function on the stored key), collapses duplicates to the
  highest id, reversible with the frozen legacy function inside the migration. Postgres migration test seeds a collision.
- **B-05** ✅ 2026-09-10 — `calc_mwst`, the credit shortcut and the AI-context money fields go through `round_chf()`
  (half-up). Matrix: 0.125 / 0.135 / 2.675 at 8.1 % and 2.6 %, negative amounts and rates. Tests 233 → **254** (PG).
- **B-12** ✅ 2026-09-10 — `.github/workflows/security.yml`: gitleaks, pip-audit (blocking, ecdsa/HS256 ignore),
  npm audit high with registry-retry, Trivy on the backend image, bandit/semgrep advisory. npm audit fix bumped
  5 transitive dev deps; both audits clean. Bandit mediums → B-32.
- **B-07** ✅ 2026-09-10 — Rate-limit keys `tenant:<tid>` (Bearer decoded without DB) / `ip:<addr>`. `RATE_LIMIT_DEFAULT`
  200/min on every route, `RATE_LIMIT_CLASSIFY` 60/min on `classify/{,predict,batch}`, `RATE_LIMIT_HEAVY` 30/min on
  `scanner/extract`, `pdf/parse`, `ai/{chat,summary}`, `classify/train`. Found and fixed: slowapi's middleware never
  matched a route on FastAPI ≥ 0.135 (nested routers), so the default limit was silently off — now an app-level
  dependency. 429 uses the error envelope (`rate_limited`) + `Retry-After`. Tests 216 → **233**.
- **B-06** ✅ 2026-09-10 — `POST /api/export/{banana,csv,excel}` and `/api/export/email/rows` require a login
  (same `get_current_user` dependency as everything else); anonymous → 401 covered in the isolation guard.
- **B-26** ✅ 2026-09-10 — Tenant columns → platform contract: `plan` → `subscription_plan` (rename, data kept),
  `slug` (unique, derived from name, suffix on collision), `trial_ends_at`, `is_active` (403 `Tenant deaktiviert`).
  Migration `921d958b8530` verified up/down/up; API image now runs `alembic upgrade head` on start;
  platform `--cd-*` tokens imported (1.6). Tests 203 → **216**.
- **B-31** ✅ 2026-09-10 — Platform auth contract: token `{sub,tid,role,type,jti}`, `tid`/`type` verified, legacy `tenant_id` accepted one release, `require_role()` ladder (owner›admin›editor›viewer). Tests 193 → **203**.
- **B-01** ✅ 2026-09-09 — **fix(export)**: `fmt_swiss` lost the carry (`1234.999 → 1'234.00`), amounts used
  half-even. New `round_chf()` (Decimal, `ROUND_HALF_UP`). 13 regression cases.
- **B-02** ✅ 2026-09-09 — Tests 6 → **193** (+2 skipped): factories, tenant isolation for every router,
  Banana/CSV/Excel export, classifier layers, storage.
- **B-03** ✅ 2026-09-09 — `modell/page.tsx` 955 → 20 files, largest 107 lines. tsc + lint green.
- **B-00** ✅ 2026-09-09 — `services/storage.py`: `StorageBackend` (local | s3), env-driven, `model_storage.py`
  routed through it. Note: no receipt upload path existed → B-09.

---

## Phase progress (mirrors chadev-platform/ROADMAP.md)

| Phase | Status |
|---|---|
| 0 Recon | ✅ |
| 0.5 Risk fixes before platform work | ✅ B-00…B-03 (branch `feat/phase0-risks`) |
| 1 Platform contract | 1.2 ✅ B-31 · 1.4 ✅ B-26 · 1.6 ✅ tokens imported |
| 2 Security | ✅ B-06, B-07, B-32 · open: B-24, B-25, B-34 |
| 3 Reliability | ✅ B-04, B-05, B-08, B-11, B-33, B-35 |
| 4 Polish | ✅ B-09, B-13 · open: B-22 |
| 5 UX | ✅ B-18, B-19 · NOW: B-14, B-16, B-21 · open: B-15, B-17, B-20 |
| 6 Together | ✅ B-36 (SSO + mirroring), B-37 (events) · parked: B-38 |
| 7 DX | ✅ B-12, B-29, B-30 |
