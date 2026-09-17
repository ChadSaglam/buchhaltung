# Buchhaltung

Self-learning Swiss bookkeeping SaaS. Photograph a receipt or upload a bank
statement — the system extracts the data, classifies it to the right accounts,
and exports Banana-compatible bookings. Multi-tenant from the ground up.

![Python](https://img.shields.io/badge/Python-3.14%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-green)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![License](https://img.shields.io/badge/License-Proprietary-red)

## What it does

- **Receipt scanner** — photo or PDF → a local vision model (Ollama: `gemma3`, or
  `kimi-k2.5:cloud`) extracts vendor, amount, VAT, invoice number; Tesseract OCR
  is the fallback. Low-confidence results land in a review queue, not in the books.
- **Bank statement import** — PDF Kontoauszug → transactions parsed and
  classified in one pass.
- **Self-learning classifier** — per tenant: memory (exact match, confidence 1.0)
  → scikit-learn model (TF-IDF + LogisticRegression, ≥ 0.45) → keyword rules
  (0.72 / 0.35 fallback). Every correction is stored; the model retrains
  automatically after 20 new corrections, in a background worker.
- **Banana export** — one click to Banana Accounting TSV, styled Excel or CSV;
  optional delivery by e-mail. Banana `.xls`/text exports can be imported to
  bootstrap the model.
- **Swiss by default** — CHF with 2 decimals, MwSt codes (I81, V81, M81, …),
  KMU Kontenplan, German UI.
- **Multi-tenant** — every row carries a `tenant_id`; roles `owner › admin ›
  editor › viewer`; SSO hand-off from the ChaDev billing app.

Where it is going: `ROADMAP.md` (one running list) and
`docs/BRAINSTORM-2026-09-13.md` (document-centric ledger, invoice ↔ bank
matching, idempotent Banana batches).

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Next.js   │────▶│   FastAPI    │────▶│   PostgreSQL    │
│  Frontend   │     │   Backend    │     │   (async)       │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌───────────┐ ┌──────────┐
        │  Ollama  │ │ Tesseract │ │  Worker  │
        │ (vision, │ │  (OCR     │ │ (retrain,│
        │  chat)   │ │ fallback) │ │ schedule)│
        └──────────┘ └───────────┘ └──────────┘
```

| Layer | Stack |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind 4, Zustand, SWR, Motion |
| Backend | FastAPI, SQLAlchemy 2 async, Pydantic 2, Alembic |
| Database | PostgreSQL (prod) · SQLite + aiosqlite (dev/test) |
| ML | scikit-learn (TF-IDF + LogisticRegression), per tenant |
| Vision / OCR | Ollama (pluggable provider) · Tesseract fallback |
| Auth | JWT + bcrypt, tenant-scoped; platform SSO |

## Quick start

Prerequisites: Python 3.14+, Node.js 22+, PostgreSQL 15+ (or Docker),
[Ollama](https://ollama.com) with a vision-capable model.

```bash
git clone https://github.com/ChadSaglam/buchhaltung.git
cd buchhaltung

cp backend/.env.example backend/.env             # then set JWT_SECRET
cp frontend/.env.local.example frontend/.env.local

make setup    # backend venv + frontend deps + git hooks
make dev      # backend on :8000, frontend on :3000, migrations applied
```

Or with Docker — production settings by default (`ENVIRONMENT=production`, no
`--reload`, non-root, only `web` and `api` published): copy `.env.example` to
`.env`, set `SECRET_KEY`, `POSTGRES_PASSWORD` and `APP_DB_PASSWORD`, then
`docker compose up --build` (app on `:3000`, API on `:8000`, OpenAPI docs on
`:8000/docs`). Local tweaks go in `docker-compose.override.yml` (gitignored).

The default `up` starts five services: `web`, `api`, `worker`, `db`, `redis`.
Two more are opt-in, because neither belongs on a laptop by surprise:

```bash
docker compose --profile ai up -d ollama       # vision/OCR; several GB, CPU is fine
docker compose --profile backup up -d backup   # nightly dumps — see docs/BACKUP.md
```

Ollama needs no GPU. If you have one and want it used, put the reservation in
your own `docker-compose.override.yml` — it is a property of one host, and in the
shared file it stops `up` dead on every machine that has no GPU.

### Every command

```bash
make help        # list everything
make check       # lint · format · typecheck · api-types · tests (backend + e2e)  ← before pushing
make fix         # auto-fix formatting and lint
make api-types   # regenerate frontend types from the FastAPI OpenAPI schema
make migration m="add xyz"   # new Alembic migration
make migrate     # apply migrations
make ai-context  # refresh scripts/AI_CONTEXT.md (generated repo map)
make doctor      # which interpreters/tools this repo actually uses
make stop        # free ports 8000 and 3000
```

## Configuration

Everything lives in `backend/app/core/config.py` and is set through the
environment; `backend/.env.example` documents every key. The secret is
`SECRET_KEY` (`JWT_SECRET` is accepted as an alias and wins when set).

Production is fail-fast: the API refuses to boot with a default or short
secret, a wildcard CORS origin, or `AUTO_CREATE_TABLES` enabled — Alembic owns
the schema.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
```

Optional local helpers (LLM gateway, design/coding assistants) are described in
`docs/TOOLING.md`; none are needed to run the product.

## Storage

Files the backend persists (trained model artifacts, and every uploaded
receipt / statement as `receipts/<tenant_id>/<uuid>.<ext>` before it is
extracted — `GET /api/bookings/{id}/source` streams it back) go through
`backend/app/services/storage.py`, never straight to disk.
`STORAGE_BACKEND=local` (default) writes under `STORAGE_LOCAL_DIR` (`/app/data`,
the `model_data` volume in Docker). More than one API replica means local disk
is no longer shared — switch to `STORAGE_BACKEND=s3` with `S3_BUCKET`
(+ `S3_ENDPOINT_URL` for MinIO/R2, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
`S3_REGION`). `boto3` is only imported when the S3 backend is selected.

## Platform (SSO + events)

buchhaltung is product 2 of 2 on the ChaDev platform; billing is the identity
issuer (`chadev-platform/docs/ADR-001-sso.md`). Both contracts are gated on one
shared secret — unset, neither endpoint exists (404):

| Var | Where | Purpose |
|---|---|---|
| `PLATFORM_SHARED_SECRET` | `backend/.env` | Verifies billing's SSO token and the HMAC on inbound events. Same value as in billing's `.env`; **not** the JWT secret. Never logged. |
| `BILLING_URL` | `backend/.env` | Billing's base URL (app-switcher target, e.g. `http://localhost:5050`). |
| `NEXT_PUBLIC_BILLING_URL` | `frontend/.env.local` | Same URL for the browser — Next.js only inlines `NEXT_PUBLIC_*`. Empty = no "Apps" menu. |

- **SSO** (`contracts/sso.md`): billing sends the browser to `/sso#token=…`;
  the page posts the token to `POST /api/auth/sso` and stores the session like
  `/login`. HS256 with the shared secret, `iss=billing`, `aud=buchhaltung`,
  `type=sso`, ≤ 120 s, single-use (`sso_nonces`). Errors: 401 `sso_invalid` /
  `sso_expired` / `sso_replayed`. The first hop mirrors the billing tenant and
  provisions a shadow user (`auth_source='platform'`, no usable password —
  `/api/auth/login` answers 403 `platform_user`). Roles pass through unchanged
  on the shared ladder (`owner › admin › editor › viewer`; unknown → `viewer`).
- **Events** (`contracts/events.md`): `POST /api/platform/events`, HMAC-SHA256
  over `"<timestamp>.<raw body>"` in `X-Platform-Signature: sha256=<hex>`,
  `X-Platform-Timestamp` within ±5 min. `invoice.paid` v1 books
  `1020 Bank an 1100 Debitoren`, half-up rounded, idempotent on
  `source_key=billing:invoice:<id>:paid` (202 accepted / 200 duplicate).

## Background jobs

Classifier retrains are queued in `training_jobs` and run by the worker
(`backend/app/worker.py`). With `RUN_WORKER_IN_API=true` (default,
`scripts/dev.sh`) it shares the API process; `docker compose` runs it as the
separate `worker` service and starts the API with `RUN_WORKER_IN_API=false`.
`python -m app.worker --once` runs a single pass and exits.

## Project structure

```
backend/app/
  core/       config, database, deps, security, rate_limit, errors, logging, sentry
  models/     SQLAlchemy models — one file per table
  schemas/    Pydantic request/response models
  routers/    HTTP layer only: validate → call a service → return a schema
  services/   business logic; scanner/ = pluggable extraction providers
  alembic/    migrations
backend/tests/  SQLite/PG fixtures, factories, pipeline + tenant-isolation tests

frontend/src/
  app/          App Router pages (dashboard, scanner, kontoauszug, review, modell, …)
  components/   layout/ · shared/ · ui/ primitives
  hooks/        useApi (SWR), useMediaQuery
  lib/          api.ts · api-types.ts (GENERATED) · api-schema.ts · errors.ts · i18n.ts · *-store.ts (Zustand)
frontend/e2e/   Playwright (smoke, happy path, SSO, axe accessibility gate)
```

The full, generated route/model/service map is in `scripts/AI_CONTEXT.md`.

## API (main surface)

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register` · `login` · `sso` · `GET /api/auth/me` |
| Scanner | `POST /api/scanner/extract` · `GET /api/scanner/status` · `vision-status` · `GET/PUT /api/scanner/config` |
| Bank statement | `POST /api/pdf/parse` |
| Classify | `POST /api/classify/` · `predict` · `batch` · `correct` · `train` · `GET /api/classify/info` · `memory` · `corrections` · `top-classes` · model bundle `download/{dtype}` / `upload` |
| Review queue | `GET /api/review/` · `POST /api/review/{id}/approve` · `reject` |
| Bookings | `GET/POST /api/bookings/` · `GET /api/bookings/stats` · `{id}/source` |
| Kontenplan | `GET/PUT /api/kontenplan/` · `GET /api/kontenplan/defaults` |
| Import / export | `POST /api/import/banana` · `banana-text` · `GET/POST /api/export/{banana,excel,csv}` · `POST /api/export/email` |
| AI assistant | `GET /api/ai/status` · `POST /api/ai/chat` (streamed) · `summary` |
| Ops | `GET /api/health` · `health/detail` · `GET /api/audit/` · `GET /api/stats/learning` · `POST /api/platform/events` |

Every failure has one shape — `{"error": {"code", "message", "request_id"}}` —
and every response carries `X-Request-ID`, echoed in the structured JSON logs.

## Contracts & conventions

- **API types are generated, not written.** `make api-types` regenerates
  `frontend/src/lib/api-types.ts`; CI fails if it drifts.
- **Schema changes go through Alembic.** CI fails if models drift from migrations.
- **Tenant isolation is tested**, not assumed (`backend/tests/test_tenant_isolation.py`).
- **Working on this repo with an AI agent?** Read `AGENTS.md` first and keep
  `scripts/AI_CONTEXT.md` fresh with `make ai-context`.

## License

Proprietary — © 2026 Chadev. All rights reserved.
