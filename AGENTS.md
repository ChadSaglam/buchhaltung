# AGENTS.md — how to work in this repo

Canonical brief for any AI agent (Claude, Copilot, Cursor, Codex) or new human
contributor. `CLAUDE.md` and `SKILL.md` point here. **Read this before editing.**

---

## 1. What this is

Multi-tenant Swiss bookkeeping SaaS. A user photographs a receipt or uploads a
bank-statement PDF; the system extracts the data, classifies it to the right
accounts, and exports Banana-compatible bookings.

**Not** a single-company internal tool. Every feature must work for many tenants.

| Layer | Stack |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind 4, Zustand, SWR/React Query |
| Backend | FastAPI, SQLAlchemy 2 async, Pydantic 2, Alembic |
| DB | PostgreSQL (prod) · SQLite+aiosqlite (dev/test) |
| ML | scikit-learn (TF-IDF + LogisticRegression) |
| Vision | Ollama (Kimi K2.5) + Tesseract OCR fallback |
| Auth | JWT + bcrypt, tenant-scoped |

---

## 2. Commands — use these, don't improvise

```bash
make setup       # install everything, install git hooks
make dev         # backend + frontend
make check       # lint + typecheck + tests  ← run before you claim done
make fix         # auto-fix formatting and lint
make api-types   # regenerate frontend types from the FastAPI schema
make migration m="add xyz"   # create an Alembic migration
make migrate     # apply migrations
make ai-context  # refresh scripts/AI_CONTEXT.md (the live repo map)
make doctor      # which interpreters/tools this repo is actually using
make stop        # free ports 8000 / 3000
```

If a tool is suddenly "not found" or pytest args are rejected, run `make doctor`.
Almost always it means `backend/venv` picked up a second Python version — fix
with `rm -rf backend/venv && make setup`.

---

## 3. Non-negotiable rules

1. **Tenant isolation.** Every query touching tenant data filters on
   `tenant_id`, taken from `get_current_user`. Never from the request body or a
   query param. New tables that hold tenant data get a `tenant_id` column and an
   index on it. Add a test in `backend/tests/test_tenant_isolation.py`.
2. **No invented surface.** Do not reference files, routes, columns or config
   keys that do not exist. Grep first. Say so when context is missing.
3. **Schema changes go through Alembic.** `make migration m="…"`. CI fails if
   the models drift from the migrations. `Base.metadata.create_all` runs in
   dev/test only.
4. **Config lives in `backend/app/core/config.py`.** No hardcoded URLs, secrets,
   model names, or origins anywhere else. Production refuses to boot with a
   default `SECRET_KEY` or a wildcard CORS origin.
5. **The API is the contract.** Change a router or schema → run `make api-types`
   and commit `frontend/src/lib/api-types.ts`. CI fails if it's stale.
6. **Errors are uniform.** The backend returns
   `{"error": {"code", "message", "request_id"}}` for every failure
   (`backend/app/core/errors.py`). The frontend turns any failure into an
   `AppError` via `frontend/src/lib/errors.ts`. Do not invent new shapes.
7. **User-facing strings are German** and go through `frontend/src/lib/i18n.ts`.
8. **Money is CHF with 2 decimals.** Swiss VAT codes (I81, V81, M81, …) and the
   KMU Kontenplan are domain constants — don't reinvent them.
9. **Prefer the safest correct fix** over the clever one. Match the surrounding
   patterns rather than introducing a new style.

---

## 4. Where things live

```
backend/app/
  core/       config, database, deps, security, rate_limit, errors, logging, sentry
  models/     SQLAlchemy models — one file per table
  schemas/    Pydantic request/response models
  routers/    HTTP layer only: validate → call a service → return a schema
  services/   All business logic. Routers stay thin.
    scanner/  Pluggable extraction providers (registry → vision_ollama | ocr_tesseract)
  alembic/    Migrations
  scripts/    dump_openapi.py
backend/tests/  conftest (SQLite/PG fixtures), factories, pipeline + isolation tests

frontend/src/
  app/          App Router pages; error.tsx / global-error.tsx / not-found.tsx / loading.tsx
  components/   layout/ (shell, sidebar, palette) · shared/ · ui/ (primitives)
  hooks/        useApi (SWR), useMediaQuery
  lib/          api.ts (axios) · api-types.ts (GENERATED) · api-schema.ts (aliases)
                errors.ts · i18n.ts · *-store.ts (Zustand)
```

### Adding a backend endpoint

1. Pydantic schema in `schemas/`.
2. Business logic in `services/` (tenant-scoped, testable without HTTP).
3. Thin route in `routers/`, `Depends(get_current_user)` + `Depends(get_db)`.
4. Register the router in `app/main.py` (only if the module is new).
5. `make api-types` → use the generated type in the frontend.
6. Test: happy path + a tenant-isolation case.

### Adding a frontend page

1. `app/dashboard/<name>/page.tsx`, `"use client"` only where needed.
2. Data via `useApi` (SWR) or `lib/api.ts`.
3. Types from `lib/api-schema.ts` — never hand-written response interfaces.
4. Errors through `errorMessage(err)` → `toast.error(...)`.
5. Every async surface needs three states: skeleton, empty (`EmptyState`), error.
6. Add the route to `lib/navigation.ts` so the sidebar and ⌘K palette pick it up.

---

## 5. Definition of done

- [ ] `make check` is green (lint · format · typecheck · tests).
- [ ] New tenant data is isolation-tested.
- [ ] Schema change has a migration.
- [ ] API change has regenerated types committed.
- [ ] No secret, hostname, or model name hardcoded outside `config.py`.
- [ ] Loading / empty / error states exist for anything async.
- [ ] German copy for anything the user reads.

## 6. Known debt (fix opportunistically, don't let it block you)

- `settings/page.tsx` (352) and `insights/page.tsx` (320) are the next big pages — target ≤200 lines/file (`modell/` is the reference split).
- Open work is tracked in `ROADMAP.md` (one running list, R-IDs).
- A handful of `any` remain in the scanner pages; replace with generated types.
- No billing/usage-limit enforcement yet (`usage_event` model exists, unused).
- Frontend unit tests (vitest) cover pure helpers only; components and pages are covered by Playwright e2e.
