# ROADMAP — Buchhaltung (ChaDev Platform · product 2 of 2)

> One running list. Never duplicated — items move between sections, they don't get re-added.
> Legend: severity `C`ritical / `H`igh / `M`edium / `L`ow · effort `S` (<1h) / `M` (half day) / `L` (multi-day)
> IDs: `B-xx` = work item (next free: **B-36**) · `P-xx` = parked (next free: **P-05**)
> Cross-product items (SSO, contracts, design tokens) live in `chadev-platform/ROADMAP.md`, not here.
> Updated: 2026-09-10

---

## 🎯 North star — what "done" looks like

| Owner's words | What it means in this repo | Tracks that deliver it |
|---|---|---|
| **more dynamic** | Scan → classify → book without a reload; live review queue; optimistic booking edits | B-14, B-15, B-16 |
| **more professional** | Money that rounds right in every export, audit trail, branded Steuerberater hand-off | B-01 ✅, B-04 ✅, B-05 ✅, B-09 ✅, B-17 |
| **easier to improve** | No god-files, one type source, tests that catch regressions, jobs outside the API process | B-02 ✅, B-03 ✅, B-08 ✅, B-10 ✅, B-11 ✅, B-13 ✅, B-33 ✅ |
| **more user-friendly** | Loading/empty/error states everywhere, keyboard-first review, a11y, onboarding | B-18, B-19, B-20, B-21 |

Rule: every PR names the B-ID it closes and which north-star column it serves.

---

## 🔥 NOW — do these in order (one at a time)

- [ ] **B-14** Review queue: optimistic accept/reject with rollback; keyboard `j/k/a/r`. — `M` / `M`
- [ ] **B-16** Dashboard KPIs auto-refresh (SWR `refreshInterval`), no reload. — `L` / `S`
- [ ] **B-18** Loading / empty / error states audit — every dashboard page has all three. — `M` / `M`

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
- [ ] **B-19** a11y: focus trap in dialogs, ARIA on DropZone/DataTable, `Esc` closes. — `M` / `M`
- [ ] **B-20** Onboarding: first scan guided, sample receipt, Kontenplan import wizard. — `M` / `M`
- [ ] **B-21** Replace remaining `err: any` in scanner/modell hooks with generated types. — `L` / `S`

### Security & data
- [ ] **B-24** Postgres RLS (`SET LOCAL app.tenant_id`) as defence in depth — after platform contract. — `H` / `L`
- [ ] **B-25** Backup/restore script + restore drill (models + DB). — `H` / `M`

### Performance
- [ ] **B-27** N+1 audit on bookings list + stats. — `M` / `M`
- [ ] **B-28** Index audit: `(tenant_id, date)`, `(tenant_id, status)` on bookings. — `M` / `S`

### DX
- [ ] **B-29** Pre-commit: ruff + prettier + api-types freshness. — `L` / `S`
- [ ] **B-30** `scripts/project-overview.sh` → auto-updated `STATUS.md`. — `L` / `S`

---

## 🅿️ Parked
- **P-01** Abacus export format (client request).
- **P-02** Client portal for buchhaltung (Steuerberater view).
- **P-03** Mobile PWA for receipt capture.
- **P-04** Stripe vs Lemon Squeezy — decided at platform level (chadev-platform 6.4).

---

## ✅ Done

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
| 5 UX | NOW: B-14, B-16, B-18 · open: B-15, B-17, B-19, B-20, B-21 |
| 6 Together | see platform |
| 7 DX | ✅ B-12 · open: B-29, B-30 |
