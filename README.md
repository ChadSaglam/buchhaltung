# Buchhaltung

Self-learning Swiss bookkeeping SaaS. Photograph a receipt or upload a bank
statement — the system extracts the data, classifies it to the right accounts,
and exports Banana-compatible bookings. Multi-tenant from the ground up.

![Python](https://img.shields.io/badge/Python-3.14%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-green)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![License](https://img.shields.io/badge/License-Proprietary-red)

## What it does

The app is four surfaces — **Heute · Belege · Bank · Abschluss** — plus a *Mehr*
group for everything that is not a daily job. Heute is an inbox: one row per
thing actually waiting, worst first.

**Belege — getting a receipt into the books**

- **Scanner** — photo or PDF → a Swiss QR bill is decoded exactly (no model
  involved); otherwise a local vision model (Ollama `gemma3`, or
  `kimi-k2.5:cloud`) reads vendor, amount, VAT and invoice number, with
  Tesseract OCR as the fallback. Low-confidence results land in a review queue,
  not in the books.
- **E-mail intake** — one mailbox for the deployment, the tenant in the address
  (`belege+<slug>@<domain>`). An empty allow-list accepts nothing; the first
  mail from a new sender is recorded as rejected with the reason and one click
  puts them on the list.
- **Write your own invoices** — customer and line items produce a QR invoice
  (QRR on a QR-IBAN, SCOR otherwise), a debtor booking, and an open item. The
  PDF can be sent by e-mail; the payment comes back carrying the reference and
  books itself.
- **Open items and dunning** — both directions, aged, with a three-step Mahnung
  that escalates and is always a draft until you say otherwise.

**Bank — matching money to documents**

- **Statement import** — PDF Kontoauszug parsed, deduplicated and classified in
  one pass.
- **Abgleich** — reference (exact), amount + date lifted by vendor text, or a
  Sammelauftrag that sums several invoices to one line. Confirming writes the
  bookings and teaches the vendor → account pairing.

**Abschluss — what the Treuhänder used to do**

- **Month check** — one page, red or green: bank movement against account 1020,
  unmatched lines, VAT codes that contradict their rate.
- **VAT return** — Formular 200 from the bookings, effective or Saldosteuersatz,
  with a copy block for the ePortal.
- **Year-end** — balance sheet, income statement and depreciation proposals
  (ESTV Merkblatt A/1995), as PDF and as a ZIP with every receipt of the year.
- **Banana batches** — an export is a period with a status, a checksum and a
  pre-flight that refuses on real blockers; re-downloading an old batch gives
  byte-identical content.
- **Treuhänder pack** — cover sheet, the Banana file, the receipts numbered to
  match the bookings, the audit trail, and the list of bookings with no receipt.

**Mehr** — payroll (gross→net, payslip and Jahreszusammenzug PDFs, BVG minimum
check), liquidity and tax provision, recurring payments and which one is missing
this month, the Kontenplan with a non-destructive import wizard, the learning
history, the audit log, plan usage.

**Underneath**

- **Self-learning classifier** — per tenant: memory (exact match, confidence 1.0)
  → amount memory → scikit-learn model (TF-IDF + LogisticRegression, ≥ 0.45) →
  keyword rules. Every correction is stored; the model retrains automatically
  after 20 new corrections, in a background worker.
- **Swiss by default** — CHF with 2 decimals as `Numeric(12,2)`, MwSt codes
  (I81, V81, M81, …), KMU Kontenplan, German UI.
- **Multi-tenant, enforced by the database** — every row carries a `tenant_id`,
  and on PostgreSQL Row-Level Security makes the database itself refuse a
  cross-tenant row: the app connects as a `NOSUPERUSER NOBYPASSRLS` role, so a
  forgotten `WHERE` degrades to an empty result instead of a leak
  (`docs/ADR-002-rls.md`). Roles `owner › admin › editor › viewer`; SSO hand-off
  from the ChaDev billing app.

Where it is going: `ROADMAP.md` (one running list).

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Next.js   │────▶│   FastAPI    │────▶│   PostgreSQL    │
│  Frontend   │     │   Backend    │     │   (async)       │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
        ┌──────────┬───────┼───────┬──────────┐
        ▼          ▼       ▼       ▼          ▼
   ┌─────────┐ ┌────────┐ ┌───┐ ┌───────┐ ┌────────┐
   │ Ollama  │ │Tesser- │ │ … │ │ Redis │ │ Worker │
   │(vision, │ │ act    │ │   │ │(rate  │ │(retrain│
   │ chat)   │ │(OCR)   │ │   │ │limits)│ │ · jobs)│
   └─────────┘ └────────┘ └───┘ └───────┘ └────────┘
```

Two database roles, not one: Alembic connects as the owner and the app as
`app_rw`, which owns nothing and can bypass nothing. That split is what makes
Row-Level Security mean something — see `docs/ADR-002-rls.md`.

| Layer | Stack |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind 4, Zustand, SWR, Motion |
| Backend | FastAPI, SQLAlchemy 2 async, Pydantic 2, Alembic |
| Database | PostgreSQL (prod) · SQLite + aiosqlite (dev/test) |
| ML | scikit-learn (TF-IDF + LogisticRegression), per tenant |
| Vision / OCR | Ollama (pluggable provider) · Tesseract fallback |
| Auth | JWT + bcrypt, tenant-scoped; platform SSO |

## Quick start

Prerequisites: Python 3.14 (the version CI and both image stages run — `make lock`
refuses any other), Node.js 22+, PostgreSQL 15+ (or Docker), and optionally
[Ollama](https://ollama.com) with a vision-capable model. Ollama is not required:
a Swiss QR bill is read without it.

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
make lock        # recompile backend/requirements.txt from requirements.in
make migration m="add xyz"   # new Alembic migration
make migrate     # apply migrations
make backup      # one backup now; make restore-drill verifies the newest one
make lohn-vergleich          # payroll comparison template (docs/LOHN-VERGLEICH.md)
make status      # regenerate STATUS.md (tests, routes, migrations, open items)
make ai-context  # refresh scripts/AI_CONTEXT.md (generated repo map)
make doctor      # which interpreters/tools this repo actually uses
make stop        # free ports 8000 and 3000
```

### Dependencies

`backend/requirements.txt` is **generated**. Edit `backend/requirements.in` — one
line per thing we actually import, with a floor rather than a pin — and run
`make lock`; the compiled file is what CI installs, what the images ship and what
`pip-audit` reads, so two installs a month apart are the same install.

`make lock` refuses to run unless the venv's Python matches `PYTHON_VERSION` in
the workflow. That is not fussiness: pip-compile resolves for the interpreter it
runs on, and the same file pins a different numpy on 3.11 than on 3.14.

## Configuration

Everything lives in `backend/app/core/config.py` and is set through the
environment; `backend/.env.example` documents every key. The secret is
`SECRET_KEY` (`JWT_SECRET` is accepted as an alias and wins when set).

Production is fail-fast: the API refuses to boot with a default or short
secret, a wildcard CORS origin, `AUTO_CREATE_TABLES` enabled, an empty
`MIGRATION_DATABASE_URL` or one equal to `DATABASE_URL` — Alembic owns the
schema, and the two URLs must be two different roles. It also refuses to boot as
a superuser or a `BYPASSRLS` role, because Row-Level Security would then be
enabled and enforcing nothing, which is the worst of the three possible states.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
```

Compose creates the second role for you — `docker/db-init/10-app-role.sql` runs
once, on an empty data directory. An existing volume means it never ran: create
`app_rw` by hand before switching (`docs/ADR-002-rls.md`).

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
  app/          App Router pages, one folder per surface:
                dashboard/ (Heute) · belege/{,neu,scanner,email,firma} ·
                bank/{,abgleich,buchungen} · abschluss/ · lohn/ · kontenplan/ ·
                review/ · modell/ · lernverlauf/ · audit/ · abo/ · settings/
                (the pre-2026-09-16 addresses — rechnungen/, scanner/,
                kontoauszug/, abgleich/, insights/ — still resolve as 307s)
  components/   layout/ · shared/ · ui/ primitives
  hooks/        useApi (SWR), useMediaQuery
  lib/          api.ts · api-types.ts (GENERATED) · api-schema.ts · errors.ts · i18n.ts · *-store.ts (Zustand)
frontend/e2e/   Playwright (smoke, happy path, SSO, axe accessibility gate)
```

The full, generated route/model/service map is in `scripts/AI_CONTEXT.md`.

## API (main surface)

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register` · `login` · `sso` · `GET /api/auth/me` · `PATCH /api/auth/me{,/tenant}` |
| Belege | `POST /api/documents/` (≤ 50 files) · `GET /api/documents/` · `/summary` · `/{id}` · `/{id}/file` · `PATCH /api/documents/{id}` · `POST /api/scanner/extract` (SSE optional) · `GET /api/scanner/{status,vision-status,config}` · `PUT/PATCH /api/scanner/config` |
| E-mail intake | `POST /api/email/inbound` (HMAC) · `GET /api/email/` · `PUT /api/email/einstellungen` · `POST /api/email/{absender,abrufen}` |
| Rechnungen | `GET/POST /api/rechnungen/` · `GET /api/rechnungen/{id}` · `/{id}/rechnung.html` · `/{id}/rechnung.pdf` · `GET/POST /api/rechnungen/{id}/versand` · `GET/PUT /api/rechnungen/firma` |
| Offene Posten | `GET /api/offene-posten/` · `GET /api/offene-posten/{id}/mahnung{,.html,.pdf}` · `POST /api/offene-posten/{id}/mahnung` |
| Bank | `POST /api/pdf/parse` · `POST /api/abgleich/statements` · `GET /api/abgleich/` · `POST /api/abgleich/refresh` · `POST /api/abgleich/{tx}/{confirm,reject,manual,ignore}` |
| Abschluss | `GET /api/abschluss/{monate,monat,quartale,mwst,mwst.txt,jahre,jahr,jahr.pdf,jahr.zip}` |
| Export | `GET/POST /api/export/batches/` · `GET /api/export/batches/preflight` · `GET /api/export/batches/{id}` · `/{id}/file` · `/{id}/cover` · `/{id}/pack.zip` · `GET/POST /api/export/{banana,excel,csv}` · `POST /api/export/email{,/rows}` · `POST /api/import/banana{,-text}` |
| Lohn | `GET/PUT /api/lohn/settings` · `POST /api/lohn/settings/freigabe` · `GET/POST /api/lohn/mitarbeiter` · `GET/PUT /api/lohn/mitarbeiter/{id}` · `POST /api/lohn/{vorschau,abrechnen}` · `GET /api/lohn/abrechnungen` · `/abrechnungen/{id}/lohnabrechnung.pdf` · `GET /api/lohn/mitarbeiter/{id}/jahr/{jahr}.pdf` · `GET /api/lohn/bvg-pruefung` |
| Classify | `POST /api/classify/` · `predict` · `batch` · `correct` · `train` · `GET /api/classify/info` · `memory` · `corrections` · `top-classes` · model bundle `download/{dtype}` / `upload` |
| Review queue | `GET /api/review/` · `POST /api/review/{id}/approve` · `reject` |
| Bookings | `GET/POST /api/bookings/` · `GET /api/bookings/stats` · `{id}/source` |
| Kontenplan | `GET/PUT /api/kontenplan/` · `GET /api/kontenplan/defaults` · `POST /api/kontenplan/import{,/vorschau}` |
| Heute | `GET /api/liquiditaet/` · `GET /api/dauerbuchungen/` · `GET /api/usage` |
| AI assistant | `GET /api/ai/status` · `POST /api/ai/chat` (streamed) · `summary` |
| Ops | `GET /api/health` (readiness, 503 when the database is gone) · `health/live` · `health/detail` (admin in prod) · `GET /api/audit/` · `GET /api/stats/learning` · `POST /api/platform/events` · `GET /api/onboarding/beispiel-rechnung.pdf` |

Every failure has one shape — `{"error": {"code", "message", "request_id"}}` —
and every response carries `X-Request-ID`, echoed in the structured JSON logs.

## Contracts & conventions

- **API types are generated, not written.** `make api-types` regenerates
  `frontend/src/lib/api-types.ts`; CI fails if it drifts, and so does `make check`.
- **`backend/requirements.txt` is generated too.** Edit `requirements.in`, run
  `make lock`. A package added to the input without recompiling fails the suite.
- **Schema changes go through Alembic.** CI applies every migration, rolls them
  all back, applies them again, and fails on drift.
- **Money is `Numeric(12,2)`**, rounded half-up. A test holds the whole set of
  money columns, so the next one cannot be added on `Float`.
- **Tenant isolation is tested**, not assumed
  (`backend/tests/test_tenant_isolation.py`), and on PostgreSQL enforced by the
  database (`backend/tests/test_rls.py`).
- **The backend suite runs on both databases in CI.** SQLite hides integer
  widths and has no row-level security; PostgreSQL is what production runs. Each
  has hidden a real defect from the other.
- **Working on this repo with an AI agent?** Read `AGENTS.md` first and keep
  `scripts/AI_CONTEXT.md` fresh with `make ai-context`.

## License

Proprietary — © 2026 Chadev. All rights reserved.
