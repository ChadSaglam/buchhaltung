# docs/ — what is in here and whether it is still true

The problem this file solves: a folder of a dozen documents tells you nothing about
which of them still describes the code. Every entry below says **what it is for** and
**when to read it** — and anything whose recommendations have all been carried out
lives in `archiv/` rather than here.

Rule: a document that stops being true gets fixed or archived. It does not stay.

## Decisions — read before changing the thing they decide

| File | Decides |
|---|---|
| [ADR-002-rls.md](ADR-002-rls.md) | Row-Level Security: why the app connects as `app_rw` and Alembic as the owner. *Accepted and implemented.* Read before touching tenant scoping. |
| [ADR-003-standing-orders-in-abgleich.md](ADR-003-standing-orders-in-abgleich.md) | **Open.** How standing orders become Abgleich proposals (B-74 part B). Three options, recommendation is C. Read before writing that code. |
| [IA-2026-09-14.md](IA-2026-09-14.md) | The four surfaces — Heute · Belege · Bank · Abschluss — and the rules they follow. Read before adding a page or a menu entry. |

## Specifications — open work

| File | Covers |
|---|---|
| [B-72-LOHN-SPEC.md](B-72-LOHN-SPEC.md) | Payroll. Built as option B with option C's shape; what is still missing for C is data or a certification, not code. |

## Runbooks — read when doing the thing

| File | For |
|---|---|
| [BACKUP.md](BACKUP.md) | Backup, retention, and the real restore. `make restore-drill`. |
| [RUNBOOK-RLS-CUTOVER.md](RUNBOOK-RLS-CUTOVER.md) | The RLS cutover. Sections 1–3 are behind us; **section 4 is open and needs data** — on an empty database that check passes for the wrong reason. Section 5 applies the day something breaks. |
| [DEPLOY-CHECKLIST-B36-B37.md](DEPLOY-CHECKLIST-B36-B37.md) | Deploying SSO and platform events. |
| [LOHN-VERGLEICH.md](LOHN-VERGLEICH.md) | Comparing one real payroll month against the previous provider — the check that lifts the "Nicht für die Einreichung" watermark. |
| [TOOLING.md](TOOLING.md) | Local tooling. |

## The first end-to-end run, 2026-09-17

| File | |
|---|---|
| [E2E-ERSTLAUF.md](E2E-ERSTLAUF.md) | The checklist that framed the run, and the rules for running it. Reusable for the next one. |
| [TOUR-2026-09-17.md](TOUR-2026-09-17.md) | What actually happened, stage by stage. Sixteen findings, five of them fixed on the day. Also `tour-2026-09-17.html` — the same thing as a page you can click through. |
| [FRAGEN-AN-DEN-TREUHAENDER.md](FRAGEN-AN-DEN-TREUHAENDER.md) | The 24 numbers and yes/no answers stages 6 and 7 are blocked on, each with the document it is printed on. Written to be handed over as-is. |

## archiv/

Documents whose every recommendation became a roadmap item and was closed. Kept
because the roadmap cites them as the origin of decisions, not because they still
describe anything.

| File | What it produced |
|---|---|
| [archiv/REVIEW-2026-09-12.md](archiv/REVIEW-2026-09-12.md) | B-39 … B-62. All closed. |
| [archiv/BRAINSTORM-2026-09-13.md](archiv/BRAINSTORM-2026-09-13.md) | Phase 0 (B-39, B-45, B-48, B-40, B-47, B-50) and phases 1–4 (B-64, B-73, B-76). All closed. |
| [archiv/BRAINSTORM-2026-09-12.md](archiv/BRAINSTORM-2026-09-12.md) | The session the review above came out of. |
