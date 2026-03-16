# 📒 RDS Buchhaltung

Self-learning Swiss bookkeeping SaaS powered by AI vision and machine learning.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-16.1-black)
![License](https://img.shields.io/badge/License-Proprietary-red)

## Overview

RDS Buchhaltung automates Swiss SME bookkeeping by combining AI-powered document scanning with a self-learning classification engine. Upload a receipt photo or bank statement PDF — the system extracts all data, classifies it to the correct accounts, and exports Banana-compatible bookings.

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
# Clone
git clone https://github.com/your-org/rds-buchhaltung.git
cd rds-buchhaltung

# Setup (interactive)
./scripts/setup.sh

# Or manually:
cd backend && pip install -r requirements.txt
cd ../frontend && npm install

# Start
./scripts/dev.sh
```

### With Docker

```bash
docker compose up --build
```

App available at `http://localhost:3000`, API at `http://localhost:8000`.

## Configuration

Copy `.env.example` to `.env` in the `backend/` directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/buchhaltung

# Auth
JWT_SECRET=your-secret-key-change-in-production

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Email (optional)
SMTP_HOST=mail.infomaniak.com
SMTP_PORT=465
SMTP_USER=your@email.ch
SMTP_PASSWORD=your-password
FROM_EMAIL=your@email.ch
```

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

## ML Pipeline

The classifier uses a 3-layer cascade:

1. **Memory** (confidence: 100%) — Exact match from confirmed corrections
2. **ML Model** (confidence: 45-99%) — LogisticRegression trained on your booking history
3. **Rules** (confidence: 0%) — Keyword-based fallback with `konto_defaults.json`

The system auto-retrains after 20 new corrections. Import existing Banana data to bootstrap the model instantly.

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
