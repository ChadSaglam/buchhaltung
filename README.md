# 📒 Buchhaltung

Self-learning Swiss bookkeeping SaaS powered by AI vision and machine learning.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-16.1-black)
![License](https://img.shields.io/badge/License-Proprietary-red)

## Overview

Buchhaltung automates Swiss SME bookkeeping by combining AI-powered document scanning with a self-learning classification engine. Upload a receipt photo or bank statement PDF — the system extracts all data, classifies it to the correct accounts, and exports Banana-compatible bookings.

### Key Features

- **📸 Receipt Scanner** — Photograph invoices/receipts → AI vision (Kimi K2.5) extracts vendor, amount, VAT, line items
- **📄 Bank Statement Import** — Upload UBS/PostFinance PDFs → auto-parse and classify transactions
- **🧠 Self-Learning Classifier** — 3-layer classification: Memory (exact match) → ML model (scikit-learn) → Rules (fallback)
- **🍌 Banana Export** — One-click export to Banana Accounting format (TSV), Excel, or CSV
- **📧 Email Delivery** — Send bookings directly via SMTP
- **👥 Multi-Tenant** — Full tenant isolation with role-based access
- **🇨🇭 Swiss Compliant** — MwSt codes (I81, V81, M81, etc.), Swiss Kontenplan (KMU)

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Next.js   │────▶│   FastAPI    │────▶│   PostgreSQL    │
│  Frontend   │     │   Backend    │     │   (async)       │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────┴───────┐
                    │   Ollama     │
                    │ kimi-k2.5    │
                    │  (Vision)    │
                    └──────────────┘
```

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 22+
- PostgreSQL 15+ (or Docker)
- [Ollama](https://ollama.com) with `kimi-k2.5:cloud`

### Without Docker

```bash
git clone https://github.com/your-org/rds-buchhaltung.git
cd rds-buchhaltung

cp backend/.env.example backend/.env       # then fill in JWT_SECRET
cp frontend/.env.local.example frontend/.env.local

make setup    # installs backend + frontend deps and the git hooks
make dev      # runs both
```

### Every command

```bash
make help        # list everything
make check       # lint · format · typecheck · tests   ← run before pushing
make fix         # auto-fix formatting and lint
make api-types   # regenerate frontend types from the FastAPI OpenAPI schema
make migration m="add xyz"   # new Alembic migration
make migrate     # apply migrations
make ai-context  # refresh the generated repo map for AI agents
make doctor      # diagnose the venv / toolchain
make stop        # free ports 8000 and 3000
```

### With Docker

```bash
docker compose up --build
```

App available at `http://localhost:3000`, API at `http://localhost:8000`.

## Configuration

All configuration lives in `backend/app/core/config.py` and is set through the
environment. Start from `backend/.env.example` — it documents every key.

Production is fail-fast: the API refuses to boot with a default `JWT_SECRET`, a
wildcard CORS origin, or `AUTO_CREATE_TABLES` enabled (Alembic owns the schema).

```bash
cp backend/.env.example backend/.env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
```

## Storage

Files the backend persists (trained model artifacts, and every uploaded
receipt / statement PDF as `receipts/<tenant_id>/<uuid>.<ext>` before it is
extracted — `GET /api/bookings/{id}/source` streams it back) go through
`backend/app/services/storage.py`, never straight to disk. `STORAGE_BACKEND=local` (default) writes under
`STORAGE_LOCAL_DIR` (`/app/data`, the `model_data` volume in Docker). Run more
than one API replica and local disk is no longer shared — switch to
`STORAGE_BACKEND=s3` with `S3_BUCKET` (+ `S3_ENDPOINT_URL` for MinIO/R2,
`S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`). `boto3` is only imported when
the S3 backend is selected.

## Platform (SSO + events)

buchhaltung is product 2 of 2 on the ChaDev platform; billing is the identity
issuer (`chadev-platform/docs/ADR-001-sso.md`). Two server-side contracts are
implemented here, both gated on one shared secret — unset, neither endpoint
exists (404):

| Var | Where | Purpose |
|---|---|---|
| `PLATFORM_SHARED_SECRET` | `backend/.env` | Verifies billing's SSO token and the HMAC on inbound events. Same value as in billing's `.env`; **not** the `JWT_SECRET`. Never logged. |
| `BILLING_URL` | `backend/.env` | Billing's base URL (app-switcher target, e.g. `http://localhost:5050`). |
| `NEXT_PUBLIC_BILLING_URL` | `frontend/.env.local` | Same URL for the browser — Next.js only inlines `NEXT_PUBLIC_*`. Empty = no "Apps" menu, no dead link. |

- **SSO** (`contracts/sso.md`, B-36): billing sends the browser to `/sso#token=…`;
  the page posts the token to `POST /api/auth/sso` and stores the session
  exactly like `/login`. The token is HS256 with the shared secret, `iss=billing`,
  `aud=buchhaltung`, `type=sso`, ≤ 120 s, single-use (`sso_nonces` table).
  Errors: 401 `sso_invalid` / `sso_expired` / `sso_replayed`. The first hop
  mirrors the billing tenant (`tenants.platform_tenant_id`, Kontenplan seeded)
  and provisions a *shadow user* (`users.platform_user_id`,
  `auth_source='platform'`, no usable password — `/api/auth/login` answers 403
  `platform_user`). Later hops refresh tenant name/plan/trial and the user's
  email/name/role. Roles pass through unchanged on the shared ladder
  (`owner › admin › editor › viewer`; unknown → `viewer`). A local user of the
  *same* mirrored tenant with that email is linked (keeps password and role);
  one in another tenant blocks the hop with 409 `email_taken_locally`.
- **Events** (`contracts/events.md`, B-37): `POST /api/platform/events`, HMAC-SHA256
  over `"<timestamp>.<raw body>"` in `X-Platform-Signature: sha256=<hex>`,
  `X-Platform-Timestamp` within ±5 min. `invoice.paid` v1 books
  `1020 Bank an 1100 Debitoren`, amount from the decimal string (half-up,
  `round_chf`), date `paid_at`, text `Zahlung <number> <client>`,
  `source=billing`, idempotent on `source_key=billing:invoice:<id>:paid`
  (202 accepted / 200 duplicate). 401 `bad_signature` / `stale_timestamp`,
  400 `unsupported_version`, 404 `unknown_tenant` (tenant never did SSO —
  billing treats it as final).

## Background jobs

Classifier retrains are queued in the `training_jobs` table and run by the
worker (`backend/app/worker.py`). With `RUN_WORKER_IN_API=true` (default,
`scripts/dev.sh`) it shares the API process; `docker compose` runs it as the
separate `worker` service (`python -m app.worker`) and starts the API with
`RUN_WORKER_IN_API=false`. `python -m app.worker --once` runs a single pass
and exits.

## Project Structure

```
backend/
├── app/
│   ├── core/          # Config, database, auth dependencies
│   ├── models/        # SQLAlchemy models (booking, user, tenant, etc.)
│   ├── routers/       # API endpoints (scanner, classify, export, etc.)
│   ├── schemas/       # Pydantic request/response schemas
│   └── services/      # Business logic (classifier, vision, export, email)
├── alembic/           # Database migrations
└── requirements.txt

frontend/
├── src/
│   ├── app/           # Next.js pages (dashboard, scanner, modell, etc.)
│   ├── components/    # UI components (Sidebar, MobileNav, etc.)
│   ├── hooks/         # Custom React hooks
│   ├── lib/           # API client, i18n, utilities
│   └── stores/        # Zustand state management
└── package.json
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/scanner/extract` | POST | Upload image → extract invoice data |
| `/api/classify/predict` | POST | Classify description → accounts |
| `/api/classify/train` | POST | Retrain ML model |
| `/api/classify/correct` | POST | Submit correction → memory + training |
| `/api/bookings/` | GET/POST | CRUD bookings |
| `/api/import/banana` | POST | Import Banana Buchhaltung .xls file |
| `/api/export/banana` | GET | Export as Banana TSV |
| `/api/export/excel` | GET | Export as styled Excel |
| `/api/export/csv` | GET | Export as CSV |
| `/api/kontenplan/` | GET/POST | Manage chart of accounts |
| `/api/classify/batch` | POST | Batch classify multiple transactions |
| `/api/classify/info` | GET | Model stats (accuracy, samples, memory) |
| `/api/classify/memory` | GET | View memory entries |
| `/api/classify/download/{type}` | GET | Download model/memory/bundle |
| `/api/classify/upload` | POST | Restore model from bundle |
| `/api/scanner/status` | GET | Ollama connection & model status |
| `/api/scanner/vision-status` | GET | Vision model availability |
| `/api/stats/learning` | GET | Learning progress statistics |
| `/api/pdf/parse` | POST | Parse bank statement PDF |
| `/api/auth/sso` | POST | Exchange billing's SSO token for a session (B-36) |
| `/api/platform/events` | POST | Signed `invoice.paid` events from billing (B-37) |

## ML Pipeline

The classifier uses a 3-layer cascade:

1. **Memory** (confidence: 100%) — Exact match from confirmed corrections
2. **ML Model** (confidence: 45-99%) — LogisticRegression trained on your booking history
3. **Rules** (confidence: 0%) — Keyword-based fallback with `konto_defaults.json`

The system auto-retrains after 20 new corrections. Import existing Banana data to bootstrap the model instantly.

## Contracts & conventions

- **API types are generated, not written.** `make api-types` dumps the FastAPI
  OpenAPI schema and regenerates `frontend/src/lib/api-types.ts`. CI fails if it
  drifts. Import stable aliases from `frontend/src/lib/api-schema.ts`.
- **Every error has the same shape.** Backend:
  `{"error": {"code", "message", "request_id"}}`. Frontend: `toAppError()` in
  `src/lib/errors.ts` turns any failure — HTTP, offline, timeout — into one
  German, user-showable message with a correlation id.
- **Every request is traceable.** `X-Request-ID` on every response, echoed in the
  structured JSON logs and shown to the user on error.
- **Working on this repo with an AI agent?** Read [AGENTS.md](./AGENTS.md), and
  keep [`scripts/AI_CONTEXT.md`](./scripts/AI_CONTEXT.md) fresh with
  `make ai-context`.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TailwindCSS 4, Framer Motion |
| Backend | FastAPI, SQLAlchemy 2 (async), Pydantic 2 |
| Database | PostgreSQL (prod), SQLite (dev) |
| ML | scikit-learn (LogisticRegression + TF-IDF) |
| Vision | Ollama + Kimi K2.5 (cloud) |
| Auth | JWT + bcrypt, multi-tenant isolation |

## License

Proprietary — © 2026 Chadev. All rights reserved.
