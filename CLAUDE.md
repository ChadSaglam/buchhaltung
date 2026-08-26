# CLAUDE.md

Read **[AGENTS.md](./AGENTS.md)** first — it is the single source of truth for
architecture, commands, conventions and the definition of done in this repo.

Fast facts:

- Multi-tenant Swiss bookkeeping SaaS. Never assume one company.
- `make check` before you claim a task is finished.
- Tenant isolation, Alembic migrations, and regenerated API types are mandatory,
  not optional polish.
- A live, generated map of routes/models/services is in
  [`scripts/AI_CONTEXT.md`](./scripts/AI_CONTEXT.md) — refresh with `make ai-context`.
