## What changed

<!-- One or two sentences. Link the issue if there is one. -->

## Why

<!-- The problem this solves. -->

## Checklist

- [ ] `make check` is green (lint · format · typecheck · tests)
- [ ] New/changed tenant data is covered by an isolation test
- [ ] Schema change ships with an Alembic migration
- [ ] API change: `make api-types` run and `frontend/src/lib/api-types.ts` committed
- [ ] No secrets, hostnames or model names hardcoded outside `config.py`
- [ ] Async UI has loading, empty and error states
- [ ] User-facing copy is German and goes through `i18n.ts`

## Screenshots / notes

<!-- For UI changes. Delete if not applicable. -->
