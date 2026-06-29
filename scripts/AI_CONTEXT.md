# AI_CONTEXT — Buchhaltung

> Auto-generated 2026-06-29 17:08. Feed this to an AI agent before code tasks.

## §8 CTO Protocol

- Multi-tenant SaaS: every query must filter by `tenant_id`.
- Stack: FastAPI + asyncpg + SQLAlchemy, Next.js, PostgreSQL, Ollama.
- Open auto-debt items: **6**
- Open manual tasks: **3** | Done: **0**
- Priority order: resolve all `P0` before shipping new features.

## §9 Live Backlog Snapshot

### Auto-detected
- `P0` Hardcoded Ollama URL still present
- `P1` No CI workflow
- `P1` No backend tests directory
- `P1` No lint config (ruff)
- `P1` No global error boundary
- `P1` No billing router (V6)

### Manual (open)
- `[CLIENT]` Export to Abacus format
- `[CTO]` Decide Stripe vs. Lemon Squeezy for V6 billing
- `[HIGH]` Add tenant-isolation integration tests (V7)

### Roadmap progress
- `V3` 3/6 (50%)
- `V4` 6/6 (100%)
- `V5` 6/6 (100%)
- `V5.1` 5/6 (83%)
- `V5.2` 4/6 (66%)
- `V5.3` 6/6 (100%)
- `V5.4` 6/6 (100%)
- `V6` 0/4 (0%)
- `V7` 0/5 (0%)
- `V8` 4/6 (66%)
- `V9` 4/5 (80%)
- `V10` 2/5 (40%)
