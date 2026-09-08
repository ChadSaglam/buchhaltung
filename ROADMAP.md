# ROADMAP — buchhaltung (part of ChaDev Platform)

> Canonical multi-repo roadmap lives in chadev-platform. This is the buchhaltung-scoped mirror.
> Updated: 2026-09-08 · Effort: S < 1h · M < 4h · L > 4h

---

## NOW

**Current phase:** Phase 2 — Security & tenant isolation — IN PROGRESS
**Branch:** `feat/phase1-platform-contract` (same branch, continued)
**Next action:** 2.2 add test_tenant_isolation.py

---

## D1 / D2 — DECIDED

D1 = B. D2 = billing issues JWTs, buchhaltung verifies via shared SECRET_KEY (HS256) now, JWKS later.

---

## Phase 0 ✅ / Phase 1 ✅ DONE

See PR #16. Contracts reviewed, tenant migration + role/jti plan logged.

---

## Phase 2 — Security & tenant isolation — M — IN PROGRESS (buchhaltung tasks)

- [ ] 2.2 Add test_tenant_isolation.py cases for bookings, review queue, scanner config, export (M)
- [ ] 2.3 Audit every router for tenant_id from token only — grep tenant_id in request bodies (M)
- [ ] 2.5 Rate limits on login/register/refresh/scanner-extract; per tenant not per IP only (S)

## Phase 1 carryover (implementation, tracked here)

- [ ] 1.4 Alembic migration: add `trial_ends_at` (nullable), `is_active` (default true, backfill) to `tenants` (M)
- [ ] 1.4b Add roles `admin|editor|viewer` to user role enum (M)
- [ ] 1.4c Add `jti` revocation table/mechanism matching billing's (M)

## Phase 3 — Reliability & tests — L

- [ ] 3.1 Factories + tests for classifier memory/ML/rules layers (M)
- [ ] 3.2 Tests for Banana TSV export (money rounding, VAT codes) (M)
- [ ] 3.4 Vitest for critical FE utils (M)
- [ ] 3.5 Playwright happy path: login → create → export (M)

## Phase 4 — Professional polish — M

- [ ] 4.3 Background jobs to worker compose service (M)
- [ ] 4.4 Uploads to S3-compatible storage behind StorageBackend interface (M)
- [ ] 4.5 /api/health returns version, db, migration_head, storage (S)

## Phase 5 — Dynamic & user-friendly UX — L

- [ ] 5.2 Split modell/page.tsx into ≤200-line components (M)
- [ ] 5.3 Adopt shared design tokens (M)
- [ ] 5.4 Loading/empty/error states audit (M)
- [ ] 5.5 a11y pass (M)

## Phase 6 — Together: cross-product features — L

- [ ] 6.2 Accept POST booking from billing on paid invoice (M)
- [ ] 6.3 Scanned supplier invoice → suggest client/service in billing (L)
- [ ] 6.5 One onboarding (M)

## Phase 7 — Developer experience — S

- [ ] 7.3 Add security.yml copied from billing (S)
- [ ] 7.4 Pre-commit hooks (S)
- [ ] 7.5 scripts/project-overview.sh → STATUS.md (S)

---

## DONE

- [x] Phase 0 Recon (2026-09-07)
- [x] Phase 1 complete — contracts reviewed, PR #16 open (2026-09-07)

---

## SESSION HANDOFF

```
STATE: Phase 2 started on same branch (feat/phase1-platform-contract).
PR: buchhaltung#16 (open)
NEXT ACTION: implement 2.2 test_tenant_isolation.py as next commit.
```
