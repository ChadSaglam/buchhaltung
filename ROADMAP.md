# ROADMAP — buchhaltung (part of ChaDev Platform)

> Canonical multi-repo roadmap lives in chadev-platform. This is the buchhaltung-scoped mirror.
> Updated: 2026-09-07 · Effort: S < 1h · M < 4h · L > 4h

---

## NOW

**Current phase:** Phase 1 — Platform contract — IN PROGRESS
**Branch:** `feat/phase1-platform-contract`
**Next action:** Awaiting D2 (SSO direction) confirm, then implement 1.4 tenant migration.

---

## D1 — DECIDED

**B — Separate repos + shared platform contract.**

## D2 — PENDING (SSO direction)

Proposal (see chadev-platform contracts/auth.md): billing issues JWTs, buchhaltung verifies via shared `SECRET_KEY` (HS256) now, JWKS/RS256 later. buchhaltung must add `admin|editor|viewer` roles (currently `owner`-only) and `jti` revocation before this works.

---

## Phase 0 — System map ✅

| | billing | buchhaltung |
|---|---|---|
| Purpose | Offerte/Rechnungen, QR-bill PDF, client portal | Receipt/bank-statement scan → AI classification → Banana export |
| Backend | FastAPI, sync SQLAlchemy, psycopg2 | FastAPI, async SQLAlchemy, asyncpg (+SQLite dev) |
| Auth | JWT access+refresh (revocable jti), roles admin/editor/viewer, trial gate | JWT, role owner only, plan free |
| Tenant | tenants(subscription_plan, trial_ends_at, is_active) | tenants(plan) only |
| Errors | Default FastAPI {"detail"} | Uniform {"error":{code,message,request_id}} + Sentry |
| Tests | 29 backend · 1 e2e · 0 unit FE | 6 backend · 1 e2e smoke · 0 unit FE |
| Size | 4.5k py · 10k ts | 7k py · 11.6k ts |

**Biggest risks (buchhaltung):**
1. Only 6 tests for 7k LOC of money-relevant code. [High]
2. `modell/page.tsx` = 955 lines in one file. [Medium]
3. Uploads (receipts) on local disk → breaks with >1 replica. [Medium]

---

## Phase 1 — Platform contract — M — IN PROGRESS (buchhaltung tasks)

- [x] Contract drafts reviewed: contracts/auth.md, contracts/tenant.md (chadev-platform) (S)
- [ ] 1.4 Alembic migration: add `trial_ends_at` (nullable), `is_active` (default true, backfill) to `tenants` — additive, reversible (M)
- [ ] 1.4b Add roles `admin|editor|viewer` to user role enum (currently `owner`-only) (M)
- [ ] 1.4c Add `jti` revocation table/mechanism matching billing's (M)
- [ ] 1.5 D2: confirm SSO verification side (shared SECRET_KEY, HS256) — **awaiting your reply**

## Phase 2 — Security & tenant isolation — M (buchhaltung tasks)

- [ ] 2.2 Add test_tenant_isolation.py cases for bookings, review queue, scanner config, export (M)
- [ ] 2.3 Audit every router for tenant_id from token only (M)
- [ ] 2.5 Rate limits on login/register/refresh/scanner-extract, per tenant not per IP (S)

## Phase 3 — Reliability & tests — L (buchhaltung tasks)

- [ ] 3.1 Factories + tests for classifier memory/ML/rules layers (M)
- [ ] 3.2 Tests for Banana TSV export (money rounding, VAT codes) (M)
- [ ] 3.4 Vitest for critical FE utils (M)
- [ ] 3.5 Playwright happy path: login → create → export (M)

## Phase 4 — Professional polish — M (buchhaltung tasks)

- [ ] 4.3 Background jobs to worker compose service (already has worker.py) (M)
- [ ] 4.4 Uploads to S3-compatible storage behind StorageBackend interface (M)
- [ ] 4.5 /api/health returns version, db, migration_head, storage (S)

## Phase 5 — Dynamic & user-friendly UX — L (buchhaltung tasks)

- [ ] 5.2 Split modell/page.tsx into ≤200-line components (M)
- [ ] 5.3 Adopt shared design tokens (M)
- [ ] 5.4 Loading/empty/error states audit (M)
- [ ] 5.5 a11y pass (M)

## Phase 6 — Together: cross-product features — L (buchhaltung tasks)

- [ ] 6.2 Accept POST booking from billing on paid invoice (webhook.py exists) (M)
- [ ] 6.3 Scanned supplier invoice → suggest client/service in billing (L)
- [ ] 6.5 One onboarding: create tenant once, enable products as modules (M)

## Phase 7 — Developer experience — S (buchhaltung tasks)

- [ ] 7.3 Add security.yml copied from billing (S)
- [ ] 7.4 Pre-commit hooks (S)
- [ ] 7.5 scripts/project-overview.sh → STATUS.md (S)

---

## DONE

- [x] Phase 0 Recon (2026-09-07)
- [x] D1 decided — Option B (2026-09-07)
- [x] Branch feat/phase1-platform-contract created (2026-09-07)
- [x] Reviewed chadev-platform contract drafts (2026-09-07)

---

## SESSION HANDOFF

```
STATE: Phase 1 in progress. Contracts drafted on chadev-platform. Awaiting D2 (SSO direction).
NEXT ACTION: confirm D2, then implement 1.4 tenant migration (reversible) + role/jti additions.
```
