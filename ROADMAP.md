# ROADMAP — Buchhaltung (ChaDev Platform · product 2 of 2)

> One running list. Never duplicated — items move between sections, they don't get re-added.
> Legend: severity `C`ritical / `H`igh / `M`edium / `L`ow · effort `S` (<1h) / `M` (half day) / `L` (multi-day)
> IDs: `B-xx` = work item (next free: **B-63**) · `P-xx` = parked (next free: **P-05**)
> Cross-product items (SSO, contracts, design tokens) live in `chadev-platform/ROADMAP.md`, not here.
> Updated: 2026-09-12 — reprioritised after the deep review (`docs/REVIEW-2026-09-12.md`). B-39…B-62 come from it.
> Companion docs: `docs/ADR-002-rls.md` (B-24) · `docs/DEPLOY-CHECKLIST-B36-B37.md` · `docs/BRAINSTORM-2026-09-12.md`.

---

## 🎯 North star — what "done" looks like

| Owner's words | What it means in this repo | Tracks that deliver it |
|---|---|---|
| **more professional** | Money that rounds right in every export, correct VAT codes, audit trail, Treuhänder hand-off that is accepted first time | B-01 ✅, B-04 ✅, B-05 ✅, B-09 ✅, B-47, B-48, B-51, B-53, B-17, B-22 |
| **more dynamic** | Scan → classify → book without a reload; live review queue; optimistic booking edits; the learning loop visibly closes | B-45, B-14, B-15, B-16 |
| **easier to improve** | No god-files, one type source, tests that catch regressions, jobs outside the API process, prod == compose | B-02 ✅, B-03 ✅, B-08 ✅, B-10 ✅, B-11 ✅, B-13 ✅, B-33 ✅, B-39, B-41, B-49, B-59, B-60 |
| **together** (platform) | One login across billing + buchhaltung, paid invoices book themselves, roles mean something | B-36 ✅, B-37 ✅, B-40, B-52, B-38 🅿️ |
| **more user-friendly** | Loading/empty/error states everywhere, keyboard-first review, a11y, onboarding, no fake saves | B-18 ✅, B-19 ✅, B-44, B-46, B-50, B-58, B-20 |

Rule: every PR names the B-ID it closes and which north-star column it serves.
Order of columns changed 2026-09-12: *professional* now outranks *dynamic* — a wrong VAT code costs money on every receipt; optimistic UI saves 300 ms.

---

## 🔥 NOW — production blockers, in this order (one at a time)

- [ ] **B-39** `training_data` table has **no migration** and `TrainingRow` is not exported from `app.models`
      (invisible to Alembic and to the CI drift check). With `ENVIRONMENT=production` (`create_all` off) Banana import,
      every training job and `/api/classify/top-classes` 500. Fix: export the model, add `create_table` +
      `ix_training_data_tenant_id` migration, make the drift job import `app.services`, add a "every `Base.metadata`
      table exists after `upgrade head`" test. — `C` / `S`
- [ ] **B-40** Wire the role ladder: `require_editor` on every mutating route, `require_admin` on Kontenplan replace,
      model/memory/corrections delete, scanner config, `import?replace=true`. `core/deps.py:55-75` exists, zero callers —
      an SSO `viewer` can wipe a tenant today. Add a route-table test: every non-GET route carries a role dependency. — `H` / `M`
- [ ] **B-41** Production compose: `ENVIRONMENT=production` on api + worker, `${SECRET_KEY:?}`, drop `--reload` from the
      image CMD, worker bypasses the migrate ENTRYPOINT (or one-shot `migrate` service + `pg_advisory_xact_lock` in `env.py`),
      no published ports for db/redis/ollama, `backend/.dockerignore` (`venv .env* tests *.db`), `USER app`, multi-stage. — `H` / `S`
- [ ] **B-42** SSRF: `ollama_base_url` (and latent `ocr_command`) become read-only from `settings` — drop them from the
      update schemas; never echo upstream bodies or exception text (`ai_assistant.py:208-209,252`). — `H` / `S`
- [ ] **B-43** Email export hardening: `EmailStr` single recipient, `html.escape` every cell, `heavy_limit` + `require_editor`
      on `/api/export/email*`, default SSL context (no `CERT_NONE`), SMTP settings from `Settings` not `os.environ`. — `H` / `S`

---

## ⏭ NEXT — make the two promises true (correctness first, then the NOW-items of 09-11)

### Correctness (professional)
- [ ] **B-45** Kontoauszug save posts `original_soll: r.KtSoll` (the *edited* value) — no `Correction` is ever logged, the
      learning loop is dead on that path. Send `r.suggSoll`/`suggHaben`, only for changed rows, `Promise.allSettled` +
      summary toast (or a `/classify/correct/batch` endpoint). — `H` / `S`
- [ ] **B-48** Scanner VAT: exact map `{8.1:I81, 2.6:I26, 3.8:I38, 7.7:I77, 2.5:I25, 3.7:I37}` instead of `≥7→8.1`, `≥2→2.6/I25`;
      keep the detected rate; `_validate_and_fix` must not zero amounts > 50 000 — set `needs_review`. — `H` / `M`
- [ ] **B-47** Input bounds: `betrag`/`mwst_amount` `Field(allow_inf_nan=False, ge=-1e9, le=1e9)` on every money schema;
      `limit: int = Query(500, ge=1, le=1000)` on every list route (`audit.py:29` is the pattern); `round_chf` rejects non-finite. — `H` / `S`
- [ ] **B-49** Off the event loop: sklearn `fit`+CV (`/train`, `import?auto_train`, in-API worker), the sync Ollama chain in
      `ScannerService` (use the existing `*_async` variants, one status probe per request), `smtplib`, `pdfplumber` →
      `asyncio.to_thread`; compose sets `RUN_WORKER_IN_API=false`. — `H` / `M`

### User-friendly (the 09-11 NOW items, with what the review found)
- [ ] **B-44** Logout clears SWR cache + notifications store; `useApi` keyed by user id (tenant B sees tenant A's KPIs today). — `H` / `S`
- [ ] **B-46** Settings: 4 of 6 tabs "save" with a 600 ms sleep and show "Gespeichert". Wire profile/company or hide them;
      remove the password tab until `/api/auth/password` exists. — `H` / `S`
- [ ] **B-50** `errorMessage(err)` at the 7 `.response.data.detail` sites (login, register, BuchungTable, useBananaImport,
      useModellActions ×3) — the backend never sends `detail`; `corrections_count` → `correction_count` on the dashboard.
      **Folds B-21** (the 5 `err: any` are the same sites). — `M` / `S`
- [ ] **B-14** Review queue: optimistic accept/reject with rollback; keyboard `j/k/a/r`. Sketch in `docs/REVIEW-2026-09-12.md` §5.
      **First** move the global bare-`a` assistant hotkey (`ShortcutsModal.tsx:53`) to `Shift+A`. — `M` / `M`
- [ ] **B-16** Dashboard KPIs auto-refresh via `useApi(path, { refreshInterval })`. **First** put `SystemChecklist`,
      `GettingStarted` and the bell poll on the same SWR keys (dashboard load fires `/classify/info` ×4, `/bookings/stats` ×4,
      `/vision-status` ×3 today). — `L` / `S`
- [ ] **B-15** Scan progress streamed (NDJSON already used by AI chat) instead of spinner. — `M` / `M`
- [ ] **B-34** `classifier_models.model_sha256` column + check in `model_blob.unpack()`; "Modell neu trainieren" hint on
      unsigned blob. Also: derive the blob HMAC key from `SECRET_KEY` (`HMAC(SECRET_KEY, b"model-blob-v1")`) and refuse
      `pack/unpack` with an `INSECURE_SECRETS` key in every environment. — `L` / `S`

---

## 📋 LATER — by track

### Professional
- [ ] **B-17** Treuhänder export pack: Banana TSV + PDF summary + receipts zip + audit extract, one click — the hero flow
      (see brainstorm idea A). Validate with two Treuhänder *before* building the PDF. — `M` / `L`
- [ ] **B-53** Export safety: neutralise `= + - @` cells in xlsx/csv/tsv (formula injection, verified), escape `\t`/`\n` in
      Banana TSV text fields, `zfill(2)` dates, blank non-finite amounts. — `M` / `S`
- [ ] **B-51** Money columns `Float` → `Numeric(12,2)` (bookings, review_queue_items) with `round_chf` before insert;
      stats summed as Decimal (`0.1+0.2+0.3` is `0.6000000000000001` today). Migration + data copy. — `M` / `M`
- [ ] **B-56** Parser/classifier hygiene: `_parse_swiss_number` handles `'`/`’`/`\u202f` and `1234,50`; date regex anchored
      (4-digit year → `3924` today); tenant-specific supplier names out of `CLASSIFICATION_RULES` into per-tenant
      `KontoDefault`/memory; `save_to_memory` skips empty keys. — `M` / `S`
- [ ] **B-22** Audit log surfaced in UI (model exists: `audit_log.py`). — `M` / `M`
- [ ] **B-23** Usage limits enforced from `usage_event` (plan free/pro) — needed before billing R-106 Stripe means anything;
      pair with B-54 quotas. — `M` / `M`

### Together / data integrity
- [ ] **B-52** Idempotency by constraint: partial unique index `(tenant_id, source_key) WHERE source='billing'` +
      `IntegrityError → 200 duplicate` (two concurrent `invoice.paid` → two bookings today); approve/reject as
      `UPDATE … WHERE status='pending'` on rowcount; idempotency key on bulk `POST /api/bookings/`. — `M` / `S`
- [ ] **B-57** Worker hardening: `configure_sentry` in `worker.main`, `await gather` on stop, `stop_grace_period: 120s`,
      reap `running` jobs older than N min back to `pending`, single-class training → 400 not 500, commit the import
      *before* `auto_train`. — `M` / `S`

### User-friendly
- [ ] **B-58** UX/a11y batch (ui-ux-pro-max §1–§3): one `formatCHF()` (`de-CH`, right-aligned amounts) replacing 3 formatters +
      raw `toFixed`; `cursor-pointer` in `Button` base; popovers get `aria-haspopup/expanded` + Esc (`usePopover`);
      `aria-current` in nav, `aria-label` on the 3 `<nav>`s; `w-[28rem]` picker → `min(28rem, calc(100vw-2rem))`;
      emoji → Lucide; amber/emerald accents to ≥ 4.5:1; `InvoiceCard` header → `<button aria-expanded>`; Modell sub-tabs
      on SWR with skeleton/error; confirm + `loading` on restore/replace-import/DangerZone/"Neue Datei". — `M` / `M`
- [ ] **B-59** `response_model=` on the dict-returning routers (classify/info, bookings/stats, review/, audit/, stats/learning,
      kontenplan) → `make api-types` → delete the hand-written interfaces (3 shapes for `/classify/info` today). — `M` / `M`
- [ ] **B-20** Onboarding: first scan guided, sample receipt, Kontenplan import wizard. — `M` / `M`

### Security & data
- [ ] **B-24** Postgres RLS as defence in depth — **ADR-002 drafted** (`docs/ADR-002-rls.md`): RLS + `SET LOCAL` on
      `after_begin`, migrator/app role split, 12 tables, PG-only proof test. After B-39/40/41. — `H` / `L`
- [ ] **B-25** Backup/restore: nightly `pg_dump -Fc` + `model_data` (receipts!) sync, `make backup` / `make restore-drill`,
      retention documented. Nothing exists today. — `H` / `M`
- [ ] **B-54** Upload bounds: reject on `Content-Length` + streamed cap *before* `file.read()`, cap `ZipInfo.file_size`
      before `zf.read`, cap list sizes (kontenplan, memory JSON, bulk bookings), per-tenant storage quota via `usage_event`;
      `pdf/parse` persists before parsing today. — `M` / `M`
- [ ] **B-55** Auth surface: `RATE_LIMIT_AUTH` 10/min on login/register/sso, min password 12, uvicorn `--forwarded-allow-ips`
      (keys on the proxy IP today), slowapi `storage_uri=redis` or delete the unused redis service. — `M` / `S`
- [ ] **B-61** Health: 503 on `degraded`, cheap `SELECT 1` in production (skipped entirely today), `/api/health/detail`
      gated in prod, health exempt from the default limit. — `L` / `S`

### DX / CI
- [ ] **B-60** CI parity: backend matrix `db: [sqlite, postgres]` (up/down migration + subprocess-worker tests never run
      locally, SQLite suite never in CI; `921d958b8530` + `now()` defaults break on SQLite), `compose-smoke` job
      (`up --wait`, curl health, `worker --once`), build the frontend image, Settings ↔ `.env.example` test (7 keys missing),
      pin runtime deps (lockfile) and ruff in `requirements-dev.txt`, remove the DB password from `scripts/setup.sh:21`. — `L` / `M`
- [ ] **B-62** Frontend image: `ARG`/`ENV NEXT_PUBLIC_API_URL NEXT_PUBLIC_BILLING_URL` before `npm run build` + compose
      `build.args` (runtime env is ignored — Apps switcher never renders in the compose image), `node:22-alpine`, `npm ci`. — `M` / `S`

### Performance
- [ ] **B-27** Query audit: `import_data.py:341` one memory SELECT per key → preload once; `/stats` 3 statements → one
      `GROUP BY source`; `/stats/learning` drop 3 redundant counts; `ai_assistant.py:129` full-tenant scan per chat message
      → SQL bucketing, 12-month cap; cache `_load_model` per process keyed on `updated_at`. — `M` / `M`
- [ ] **B-28** Indexes: add `bookings(tenant_id, id DESC)` and `(tenant_id, source, id)`, drop redundant `ix_bookings_id`;
      `review_queue_items(tenant_id, status, confidence)`; `training_jobs(tenant_id, status)`. — `M` / `S`

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
| 2 Security | ✅ B-06, B-07, B-32 · NOW: B-40, B-41, B-42, B-43 · open: B-24 (ADR-002), B-25, B-34, B-54, B-55 |
| 3 Reliability | ✅ B-04, B-05, B-08, B-11, B-33, B-35 · NOW: B-39 · open: B-47, B-48, B-49, B-51, B-52, B-56, B-57 |
| 4 Polish | ✅ B-09, B-13 · open: B-22, B-53, B-61 |
| 5 UX | ✅ B-18, B-19 · NEXT: B-44, B-45, B-46, B-50 (folds B-21), B-14, B-16 · open: B-15, B-17, B-20, B-58, B-59 |
| 6 Together | ✅ B-36 (SSO + mirroring), B-37 (events) · deploy: `docs/DEPLOY-CHECKLIST-B36-B37.md` · parked: B-38 |
| 7 DX | ✅ B-12, B-29, B-30 · open: B-60, B-62 |
