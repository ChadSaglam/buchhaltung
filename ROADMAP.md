# ROADMAP — buchhaltung (part of ChaDev Platform)

> Canonical multi-repo roadmap lives in chadev-platform. This is the buchhaltung-scoped mirror.
> Updated: 2026-09-07 · Effort: S < 1h · M < 4h · L > 4h

---

## NOW

**Current phase:** Phase 0 ✅ done → starting Phase 1
**Branch:** `feat/phase1-platform-contract`
**Next action:** Phase 1.4 (tenant migration)

---

## D1 — DECIDED

**B — Separate repos + shared platform contract.** buchhaltung stays independently deployable; shares JWT/tenant/error contract via `chadev-platform`.

---

## Phase 0 — System map ✅

| | billing | buchhaltung |
|---|---|---|
| Purpose | Offerte/Rechnungen, QR-bill PDF, client portal | Receipt/bank-statement scan → AI classification → Banana export |
| Backend | FastAPI, sync SQLAlchemy, psycopg2 | FastAPI, async SQLAlchemy, asyncpg (+SQLite dev) |
| Frontend | React 19 + Vite + React Router, shadcn/ui, TanStack Query | Next.js 16 App Router, custom UI, Zustand + SWR |
| Auth | JWT access+refresh (revocable jti), roles admin/editor/viewer, trial gate | JWT, role owner only, plan free |
| Tenant | tenants(subscription_plan, trial_ends_at, is_active) | tenants(plan) only |
| User | hashed_password, full_name | password_hash, display_name |
| Errors | Default FastAPI {"detail"} | Uniform {"error":{code,message,request_id}} + Sentry |
| i18n | none (German hardcoded) | lib/i18n.ts |
| Types | api.generated.ts (openapi-typescript) | api-types.ts + make api-types CI check |
| Tests | 29 backend · 1 e2e · 0 unit FE | 6 backend · 1 e2e smoke · 0 unit FE |
| CI | ci.yml + security.yml (ruff, alembic, pytest cov, tsc) | ci.yml |
| Jobs | in-process loop + pg advisory lock (overdue, recurring) | scheduler + training worker in-process |
| Docs | SPEC.md, README, SECURITY.md | AGENTS.md, CLAUDE.md, AI_CONTEXT.md, Makefile |
| Size | 4.5k py · 10k ts | 7k py · 11.6k ts |

**Shared today:** nothing. Two tenants tables, two users tables, two logins, two design systems.

**Biggest risks (buchhaltung, verify in Phase 1/2):**
1. Only 6 tests for 7k LOC of money-relevant code. [High]
2. `modell/page.tsx` = 955 lines in one file. [Medium]
3. Uploads (receipts) on local disk → breaks with >1 replica. [Medium]

**Cross-repo risks (billing, tracked here for context):**
4. billing: /docs + /openapi.json open in production. [Medium]
5. billing: print() logging in jobs, no request-id, no Sentry. [Medium]

---

## Phase 1 — Platform contract — M — IN PROGRESS (buchhaltung tasks)

- [ ] 1.4 Align tenant table columns (plan, trial_ends_at, is_active) → Alembic migration, reversible (M)
- [ ] 1.5 SSO: verify JWT issued by billing using shared SECRET_KEY/JWKS (S, decision only)

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

- [x] Phase 0 Recon — system map written (2026-09-07)
- [x] D1 decided — Option B (2026-09-07)
- [x] Branch `feat/phase1-platform-contract` created off main (2026-09-07)

---

## SESSION HANDOFF

```
STATE: Phase 0 done. D1 = B. On feat/phase1-platform-contract.
NEXT ACTION: 1.4 tenant migration (reversible Alembic revision).
```
