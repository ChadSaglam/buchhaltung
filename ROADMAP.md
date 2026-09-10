# ROADMAP — Buchhaltung (ChaDev Platform · product 2 of 2)

> One running list. Never duplicated — items move between sections, they don't get re-added.
> Legend: severity `C`ritical / `H`igh / `M`edium / `L`ow · effort `S` (<1h) / `M` (half day) / `L` (multi-day)
> IDs: `B-xx` = work item (next free: **B-32**) · `P-xx` = parked (next free: **P-05**)
> Cross-product items (SSO, contracts, design tokens) live in `chadev-platform/ROADMAP.md`, not here.
> Updated: 2026-09-09

---

## 🎯 North star — what "done" looks like

| Owner's words | What it means in this repo | Tracks that deliver it |
|---|---|---|
| **more dynamic** | Scan → classify → book without a reload; live review queue; optimistic booking edits | B-14, B-15, B-16 |
| **more professional** | Money that rounds right in every export, audit trail, branded Steuerberater hand-off | B-01 ✅, B-04, B-05, B-17 |
| **easier to improve** | No god-files, one type source, tests that catch regressions, jobs outside the API process | B-02 ✅, B-03 ✅, B-08, B-09, B-10 |
| **more user-friendly** | Loading/empty/error states everywhere, keyboard-first review, a11y, onboarding | B-18, B-19, B-20, B-21 |

Rule: every PR names the B-ID it closes and which north-star column it serves.

---

## 🔥 NOW — do these in order (one at a time)

- [ ] **B-04** `classifier.preprocess()` strips month abbreviations without word boundaries:
      `"E-Mail" → "e-l"`, `"SEPARAT" → "arat"`. Degrades ML features and collides memory keys.
      Needs a data migration for `memory.lookup_key` (re-derive keys), not just a code fix. — `M` / `M`
      `backend/app/services/classifier.py:29-36` · test exists in `test_classifier.py` (xfail it first)
- [ ] **B-05** `calc_mwst` and the credit shortcut use Python `round()` (half-even). Swiss commercial
      rounding is half-up; align with `export.round_chf()` and extend the test matrix. — `M` / `S`
      `backend/app/services/export.py` · `test_export.py`
- [ ] **B-06** `POST /api/export/{banana,csv,excel}` and `/api/export/email/rows` accept caller-supplied
      rows with **no auth**. No tenant data leaks, but it is an open compute endpoint. Require auth. — `M` / `S`
      `backend/app/routers/export.py`
- [ ] **B-07** Rate limiter keys are per-IP only; add per-tenant keys for `scanner/extract`,
      `classify`, `ai/*` (expensive endpoints). — `M` / `S`
      `backend/app/core/rate_limit.py`

---

## ⏭ NEXT — "easier to improve" foundation

- [ ] **B-08** Move scheduler + training worker out of the API process: `worker.py` becomes its own
      compose service; API only enqueues. — `M` / `M`
      `backend/app/worker.py` · `docker-compose.yml`
- [ ] **B-09** Wire receipt/PDF persistence through `services/storage.py` (today bytes stay in memory
      and are lost after extraction — no re-processing, no audit copy). Key: `receipts/<tenant>/<uuid>.pdf`. — `M` / `M`
- [ ] **B-10** `settings/page.tsx` (352) and `insights/page.tsx` (320) → ≤200-line files, same split
      pattern as `modell/`. — `M` / `M`
- [ ] **B-11** Vitest for pure helpers: `booking-analytics`, `lib/errors.ts`, `modell/helpers.ts`. — `M` / `M`
- [ ] **B-12** `security.yml` (pip-audit + npm audit + gitleaks) copied from billing. — `L` / `S`
- [ ] **B-13** `/api/health` returns version, db, migration_head, storage backend (trim in production). — `L` / `S`

---

## 📋 LATER — by track

### Dynamic
- [ ] **B-14** Review queue: optimistic accept/reject with rollback; keyboard `j/k/a/r`. — `M` / `M`
- [ ] **B-15** Scan progress streamed (NDJSON already used by AI chat) instead of spinner. — `M` / `M`
- [ ] **B-16** Dashboard KPIs auto-refresh (SWR `refreshInterval`), no reload. — `L` / `S`

### Professional
- [ ] **B-17** Steuerberater export pack: Banana TSV + PDF summary + receipts zip, one click. — `M` / `L`
- [ ] **B-22** Audit log surfaced in UI (model exists: `audit_log.py`). — `M` / `M`
- [ ] **B-23** Usage limits enforced from `usage_event` (plan free/pro). — `M` / `M`

### User-friendly
- [ ] **B-18** Loading / empty / error states audit — every dashboard page has all three. — `M` / `M`
- [ ] **B-19** a11y: focus trap in dialogs, ARIA on DropZone/DataTable, `Esc` closes. — `M` / `M`
- [ ] **B-20** Onboarding: first scan guided, sample receipt, Kontenplan import wizard. — `M` / `M`
- [ ] **B-21** Replace remaining `err: any` in scanner/modell hooks with generated types. — `L` / `S`

### Security & data
- [ ] **B-24** Postgres RLS (`SET LOCAL app.tenant_id`) as defence in depth — after platform contract. — `H` / `L`
- [ ] **B-25** Backup/restore script + restore drill (models + DB). — `H` / `M`
- [ ] **B-26** Tenant columns → platform contract (`plan`, `trial_ends_at`, `is_active`), reversible migration.
      Tracked as platform item 1.4; implement here. — `M` / `M`

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
| 1 Platform contract | 1.2 ✅ B-31 · next: B-26 (tenant columns) |
| 2 Security | open: B-06, B-07, B-24, B-25 |
| 3 Reliability | open: B-04, B-05, B-08, B-11 |
| 4 Polish | open: B-09, B-13, B-22 |
| 5 UX | open: B-14…B-21 |
| 6 Together | see platform |
| 7 DX | open: B-12, B-29, B-30 |
