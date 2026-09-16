# ROADMAP — Buchhaltung (ChaDev Platform · product 2 of 2)

> One running list. Never duplicated — items move between sections, they don't get re-added.
> Legend: severity `C`ritical / `H`igh / `M`edium / `L`ow · effort `S` (<1h) / `M` (half day) / `L` (multi-day)
> IDs: `B-xx` = work item (next free: **B-80**) · `P-xx` = parked (next free: **P-05**)
> Cross-product items (SSO, contracts, design tokens) live in `chadev-platform/ROADMAP.md`, not here.
> Updated: 2026-09-16 (night run) — **B-51** money columns are Numeric(12,2), **B-59** `response_model` on the seven endpoints that returned bare dicts (and the hand-written frontend interfaces are gone), **B-58** the UX/a11y batch (one formatter, WCAG-AA accents, `usePopover`, heading order, confirms on destructive actions), **B-71** 90-day liquidity + tax provision on Heute, and **step 5 of the IA migration** (sidebar = four surfaces + Mehr; every old route still resolves). Earlier on 2026-09-16: B-70 Jahresabschluss and B-77 (PDF renderer = fpdf2); B-69 e-mail intake; B-52 idempotency by constraint; B-53 export safety. 2026-09-15 — B-68 write invoices (Swiss QR, debtor booking, reference return); B-67 VAT return (form 200); B-66 month-end check; B-65 open items / reminders; B-76 Banana batch (phase 4) done — and the open extension question answered: an extension may not call HTTP, so the file hand-off is final (new: B-78, read-only REST spike); B-73 Abgleich done, `make check` green. 2026-09-14 — NEXT cleared: B-44, B-46, B-16, B-34, B-49, B-14, B-15 done; B-63 amount memory. 2026-09-13 — phase 0 of `docs/BRAINSTORM-2026-09-13.md` done (B-39, B-45, B-48, B-40, B-47, B-50). 2026-09-12: reprioritised after the deep review (`docs/REVIEW-2026-09-12.md`). B-39…B-62 come from it.
> Companion docs: `docs/ADR-002-rls.md` (B-24) · `docs/B-72-LOHN-SPEC.md` (B-72) · `docs/IA-2026-09-14.md` · `docs/DEPLOY-CHECKLIST-B36-B37.md` · `docs/BRAINSTORM-2026-09-12.md`.

---

## 🎯 North star — what "done" looks like

| Owner's words | What it means in this repo | Tracks that deliver it |
|---|---|---|
| **more professional** | Money that rounds right in every export, correct VAT codes, audit trail, Treuhänder hand-off that is accepted first time | B-01 ✅, B-04 ✅, B-05 ✅, B-09 ✅, B-47 ✅, B-48 ✅, B-67 ✅, B-68 ✅, B-70 ✅, B-77 ✅, B-51 ✅, B-53 ✅, B-17, B-22 |
| **more dynamic** | Scan → classify → book without a reload; live review queue; optimistic booking edits; the learning loop visibly closes | B-45 ✅, B-14 ✅, B-15 ✅, B-16 ✅ |
| **easier to improve** | No god-files, one type source, tests that catch regressions, jobs outside the API process, prod == compose | B-02 ✅, B-03 ✅, B-08 ✅, B-10 ✅, B-11 ✅, B-13 ✅, B-33 ✅, B-39 ✅, B-41 ✅, B-49 ✅, B-59 ✅, B-60 |
| **together** (platform) | One login across billing + buchhaltung, paid invoices book themselves, roles mean something | B-36 ✅, B-37 ✅, B-40 ✅, B-52 ✅, B-38 🅿️ |
| **more user-friendly** | Loading/empty/error states everywhere, keyboard-first review, a11y, onboarding, no fake saves | B-18 ✅, B-19 ✅, B-44 ✅, B-46 ✅, B-50 ✅, B-69 ✅, B-58 ✅, B-20 |

Rule: every PR names the B-ID it closes and which north-star column it serves.
Order of columns changed 2026-09-12: *professional* now outranks *dynamic* — a wrong VAT code costs money on every receipt; optimistic UI saves 300 ms.

---

## 🔥 NOW — production blockers, in this order (one at a time)


---

## ⏭ NEXT — pull from LATER, in this order

_The 2026-09-16 night run cleared items 2 (B-71), 3 (step 5), 4 and 5 of the previous block. What is left:_

1. **B-72 Lohn light** — payroll. **Deliberately not built unattended** (2026-09-16): the rates change every year,
   a wrong AHV deduction is the customer's liability, and the roadmap itself says "validated against a real
   Treuhänder run". `docs/B-72-LOHN-SPEC.md` has the sourced groundwork; the decision is yours.
2. **B-79** Send our own invoice by e-mail. The attachment now exists (`rechnung.pdf`, 2026-09-16), so what is
   left is the draft, the recipient and a `sent_at`. The smallest remaining piece of the "no Treuhänder" loop.
3. **Finish the IA migration** — step 5 landed (sidebar = four surfaces + Mehr, old routes still resolve). Left:
   move the page files under `app/dashboard/{belege,bank}/`, and turn the Heute cards into inbox *rows*
   (steps 1–4 of `docs/IA-2026-09-14.md`). Pure refactor, do it in one sitting with the app open.
4. **B-20** Onboarding · **B-17** Treuhänder hand-off · **B-74** Dauerbuchungen (B-71 already recognises them,
   they just need a place to live on *Bank*).
5. **B-24** RLS · **B-25** backup/restore · **B-54** upload bounds · **B-55** auth surface — the security block.
   Nothing here is blocking a customer today, which is exactly why it keeps slipping.

<details><summary>What item 1 of the old block settled (Banana, 2026-09-15) — keep, do not re-litigate</summary>

A Banana *extension* may **not** call HTTP. Official wording: "For security reasons, Banana Accounting extensions
can't connect to external URLs API" (`banana.ch/doc/en/node/4065`), and extensions are "NOT ALLOWED to directly
write or read file, web resource, change computer setting or execute programs" (`node/10067`). There is no
`Banana.Http` namespace in the API reference (`node/4714`).
→ **the file hand-off is the product, not a stopgap** — there is no level-2 push to build later; stop reserving
design space for it. The HTTP that does exist runs the other way and does not close the loop: the integrated web
server (Advanced plan only, `localhost:8081`, `X-Banana-Access-Token`) is **read-only** — "the web server can't be
used to write to the accounting file, and Banana Accounting+ can't connect to external URLs" (`node/4867`) — and
the V2 *Send Data* API (`POST /v2/doc?show&acstkn=…`, `node/10157`) only creates a **new** file from an embedded
base64 AC2 + Document Change, which the user must then *Save As* over the original ("the method does not verify
that the data is correct"). The read side is the only part worth a spike → **B-78**.

</details>

_2026-09-14: the previous NEXT block (B-49, B-44, B-46, B-14, B-16, B-15, B-34) is done — see ✅ Done._

---

## 📋 LATER — by track

### "Kein Treuhänder nötig" — the product track (owner, 2026-09-14; order = impact)
Target: the Treuhänder signs once a year, nothing in between. Each item is a *flow* inside one of the four surfaces
(`docs/IA-2026-09-14.md`: Heute · Belege · Bank · Abschluss), not its own page.
- [ ] **B-79** Send the invoice by e-mail (*Belege › Rechnung schreiben*): send our own QR invoice to the customer
      instead of printing it — draft with subject and body, sent through the existing `services/email_sender.py`.
      The invoice then shows when it went out, and the Mahnung (B-65) builds on that.
      **The attachment exists since 2026-09-16**: `GET /api/rechnungen/{id}/rechnung.pdf` renders the letter and a
      SIX-conform Zahlteil, and the test decodes the QR out of the finished PDF to prove a scanner can read it.
      What is left is the sending: a draft endpoint, the recipient (there is no customer master yet — take it from
      the invoice), and a `sent_at` on the document. — `M` / `S`
- [ ] **B-74** Dauerbuchungen (*Bank*): the amounts B-63 already recognises monthly (Miete, Leasing, Versicherung) become
      expected lines — "Cembra 770.60 fehlt diesen Monat" on *Heute*, and the Abgleich proposes them with 1.0 when the
      amount+date fit even without a document. Feeds B-71 liquidity. — `M` / `S`
- [ ] **B-75** Kontoauszug ohne Upload: camt.053 pull via bLink/EBICS (UBS, PostFinance, Raiffeisen) or a scheduled
      mailbox import — the statement arrives by itself, the Abgleich inbox fills on Monday morning. PDF stays the
      fallback (customers deliver PDFs today). Needs a bank contract per tenant — spike first. — `M` / `L`
- [ ] **B-78** Read Banana data instead of exporting it (spike; only worth it for a customer on the *Advanced*
      plan): Banana's integrated web server (`localhost:8081`, RESTful, token) serves tables read-only — so
      `Buchungen` could be pulled instead of asking the customer to export `Buchungen.xls` (the model's training
      source, and a reality check against what the customer actually booked). It runs only on the customer's own
      machine, so this is an agent/CLI question, not a server-to-server call. Writing stays impossible. — `L` / `M`
- [ ] **B-72** Lohn light: monthly Lohnabrechnung with AHV/IV/EO, ALV, BVG, UVG, QST; Lohnausweis PDF; Sozialversicherungs-
      Jahresmeldung export. High liability — after B-65…B-70, and validated against a real Treuhänder run.
      **`docs/B-72-LOHN-SPEC.md`** (2026-09-16): why it was left out of the night run, the sourced 2026 figures
      (AHV/IV/EO 10.6 %, ALV 2.2 % to CHF 148 200, BVG Eckwerte), and the three options it could be — A journal
      only, B calculator with owner-entered rates (the B-71 pattern), C full payroll. **Decide A/B/C first.**
      First step is not code: reproduce one real payslip by hand. — `M` / `L`

### Professional
- [ ] **B-17** Treuhänder export pack: Banana TSV + PDF summary + receipts zip + audit extract, one click — the hero flow
      (see brainstorm idea A). Validate with two Treuhänder *before* building the PDF. — `M` / `L`
- [ ] **B-56** Parser/classifier hygiene: `_parse_swiss_number` handles `'`/`’`/`\u202f` and `1234,50`; date regex anchored
      (4-digit year → `3924` today); tenant-specific supplier names out of `CLASSIFICATION_RULES` into per-tenant
      `KontoDefault`/memory; `save_to_memory` skips empty keys. — `M` / `S`
- [ ] **B-22** Audit log surfaced in UI (model exists: `audit_log.py`). — `M` / `M`
- [ ] **B-23** Usage limits enforced from `usage_event` (plan free/pro) — needed before billing R-106 Stripe means anything;
      pair with B-54 quotas. — `M` / `M`

### Together / data integrity
- [ ] **B-57** Worker hardening: `configure_sentry` in `worker.main`, `await gather` on stop, `stop_grace_period: 120s`,
      reap `running` jobs older than N min back to `pending`, single-class training → 400 not 500, commit the import
      *before* `auto_train`. — `M` / `S`

### User-friendly
- [ ] **B-20** Onboarding: first scan guided, sample receipt, Kontenplan import wizard. — `M` / `M`

### Security & data
- [ ] **B-24** Postgres RLS as defence in depth — **ADR-002 drafted** (`docs/ADR-002-rls.md`): RLS + `SET LOCAL` on
      `after_begin`, migrator/app role split, 12 tables, PG-only proof test. After B-39/40/41. — `H` / `L`
- [ ] **B-25** Backup/restore: nightly `pg_dump -Fc` + `model_data` (receipts!) sync, `make backup` / `make restore-drill`,
      retention documented. Nothing exists today. — `H` / `M`
- [ ] **B-54** Upload bounds: reject on `Content-Length` + streamed cap *before* `file.read()`, cap `ZipInfo.file_size`
      before `zf.read`, cap list sizes (kontenplan, memory JSON, bulk bookings), per-tenant storage quota via `usage_event`;
      `pdf/parse` persists before parsing today. — `M` / `M`
- [ ] **B-55** Auth surface: `RATE_LIMIT_AUTH` 10/min on login/register/sso, min password 12, uvicorn `--forwarded-allow-ips`
      (keys on the proxy IP today), slowapi `storage_uri=redis` or delete the unused redis service. — `M` / `S`
- [ ] **B-61** Health: 503 on `degraded`, cheap `SELECT 1` in production (skipped entirely today), `/api/health/detail`
      gated in prod, health exempt from the default limit. — `L` / `S`

### DX / CI
- [ ] **B-60** CI parity: backend matrix `db: [sqlite, postgres]` (up/down migration + subprocess-worker tests never run
      locally, SQLite suite never in CI; `921d958b8530` + `now()` defaults break on SQLite), `compose-smoke` job
      (`up --wait`, curl health, `worker --once`), build the frontend image, Settings ↔ `.env.example` test (7 keys missing),
      pin runtime deps (lockfile) and ruff in `requirements-dev.txt`, remove the DB password from `scripts/setup.sh:21`. — `L` / `M`
- [ ] **B-62** Frontend image: `ARG`/`ENV NEXT_PUBLIC_API_URL NEXT_PUBLIC_BILLING_URL` before `npm run build` + compose
      `build.args` (runtime env is ignored — Apps switcher never renders in the compose image), `node:22-alpine`, `npm ci`. — `M` / `S`

### Performance
- [ ] **B-27** Query audit: `import_data.py:341` one memory SELECT per key → preload once; `/stats` 3 statements → one
      `GROUP BY source`; `/stats/learning` drop 3 redundant counts; `ai_assistant.py:129` full-tenant scan per chat message
      → SQL bucketing, 12-month cap; cache `_load_model` per process keyed on `updated_at`. — `M` / `M`
- [ ] **B-28** Indexes: add `bookings(tenant_id, id DESC)` and `(tenant_id, source, id)`, drop redundant `ix_bookings_id`;
      `review_queue_items(tenant_id, status, confidence)`; `training_jobs(tenant_id, status)`. — `M` / `S`

---

## 🅿️ Parked
- **P-01** Abacus export format (client request).
- **P-02** Client portal for buchhaltung (Steuerberater view).
- **P-03** Mobile PWA for receipt capture.
- **P-04** Stripe vs Lemon Squeezy — decided at platform level (chadev-platform 6.4).
- **B-38** `invoice.unpaid` reversal event (status set back from `paid` in billing → storno of the B-37 booking).
  Not in events v1 (contracts/events.md); needs a decision on storno vs. delete first.

---

## ✅ Done

- **Rechnung als PDF** ✅ 2026-09-16 — `GET /api/rechnungen/{id}/rechnung.pdf`: the letter plus a Zahlteil built to
  the SIX template (105 mm, 62 mm receipt, 46 mm QR, 5 mm quiet zone), so B-79 has something to attach.
  `rechnung.html` stays the browser preview. The QR is drawn as **vector rectangles** (horizontal runs merged),
  never rasterised; `swiss_qr.qr_matrix()`/`cross_geometry()` are now shared with the SVG renderer. The test that
  matters renders the finished PDF at 6x and decodes the QR back to the exact 31-line payload — it skips unless
  `zxing-cpp` is installed, and adding that to `requirements-dev.txt` makes it a real CI check. 11 tests.
  `pdf_render` gains `Meta.page_numbers` (off here — a page number would land inside the template) and
  `Meta.company_address`.
- **IA step 5** ✅ 2026-09-16 — sidebar collapsed from nine entries to the four surfaces of
  `docs/IA-2026-09-14.md` (Heute · Belege · Bank · Abschluss) plus a "Mehr" group. Every former menu entry is a
  tab of its surface (`SurfaceTabs`), `lib/navigation.ts` is the registry the sidebar, the mobile bar, the tab row,
  the breadcrumbs and the palette all read, `/dashboard/belege` and `/dashboard/bank` exist and redirect, Dashboard
  is called Heute. No page file moved and no URL changed — 23 tests, including a walk asserting all 16 existing
  routes still resolve. Left for the daylight sitting: the file moves and turning the Heute cards into inbox rows.
- **B-71** ✅ 2026-09-16 — Liquidität + Steuerrückstellung on *Heute*. `GET /api/liquiditaet/`: bank+cash balance,
  90 days of expected movements (open debtors in, open creditors out, monthly standing costs out) and the running
  balance through them — the headline is `tiefster_stand`, because a quarter that ends fine can still have a day
  with no money. Standing costs are *recognised*, not typed: same `preprocess`d text in ≥3 distinct months, amount
  stable within 15 %, credit side a cash account (income every month is a customer, not a cost) — this is B-74's
  input. Tax: profit since 1 January × the owner's rate, minus what is already in 2201, over the quarters left;
  8900 excluded from the expense side so the estimate does not chase its own tail. No default rate — the effective
  Swiss rate depends on canton *and* commune, so without one the card shows the published range (11.66 % LU to
  20.54 % BE, mean 14.43 %; ESTV, Kantonaler Vergleich der Steuerbelastung 2026) and links to the Firmenprofil.
  New nullable `company_profiles.gewinnsteuer_satz` (migration `b7c8d9e0f1a2`). 28 backend + 13 frontend tests.
- **B-58** ✅ 2026-09-16 — UX/a11y batch. One formatter (`lib/format.ts` gains `formatAmount`; the scanner's `Intl`
  copy printed U+2019 instead of an apostrophe, `rechnungen/neu`'s `chf()` was a third — both re-export now, and the
  five raw `.toFixed(2)` display sites go through it). Contrast: white on emerald was 3.77:1 and on amber 3.19:1;
  both ramps shift a step darker (5.48:1 / 5.02:1) and `lib/theme-store.test.ts` fails if any accent slips back.
  New `usePopover()` (aria-haspopup/expanded/controls, Escape closes and restores focus, listeners only while open)
  on the user menu, the bell and the app switcher. `aria-label` on both `<nav>`s + `aria-current`; the settings
  sidebar was a third `<nav>` and is now a `tablist`/`tabpanel` pair. `CardTitle` renders `<h2>` (it sat under the
  page `<h1>` and skipped a level). Modell's Gedächtnis/Top-Konten tabs are SWR readers with skeleton and error
  instead of a `useEffect` into local state. Confirms + busy locks on restore, replace-import, the danger zone and
  "Neue Datei". Plus `cursor-pointer` in the Button base, the picker at `min(28rem, 100vw-2rem)`, the InvoiceCard
  header as a `<button aria-expanded>`, and the 🧠/🤖/📋 source emoji replaced by Lucide icons with real labels.
- **B-59** ✅ 2026-09-16 — `response_model=` on the seven endpoints that returned a bare `dict`
  (classify/info, bookings/stats, review/ + approve/reject, audit/, stats/learning, kontenplan/ + defaults), so the
  OpenAPI document describes them instead of `{}`. Frontend types regenerated and the hand-written interfaces
  deleted — three had drifted: `ModelInfo` promised `sklearn_version`, `model_size_kb` and `memory_size_kb`, none of
  which the endpoint has ever sent. The learning histograms keep two shapes (`AccountCount`, `SourceCount`) instead
  of one with both keys optional. Two nullability bugs fell out of the generated types. 9 contract tests pin both
  the JSON body and the schema name.
- **B-51** ✅ 2026-09-16 — money columns `Float` → `Numeric(12,2)`. 0.1+0.2+0.3 summed to 0.6000000000000001 in the
  database, so every total the API reported was a rounded lie. `app/models/types.py:Chf` is a `TypeDecorator`:
  Numeric on PostgreSQL, Float on SQLite (no decimal type there), rounding on bind and plain floats on the way out
  so no service changed. Migration `a6b7c8d9e0f1` converts with `ROUND(col::numeric, 2)`. 6 tests, one of them a raw
  `SUM(betrag)::text` that must read exactly `"0.60"`.
- **B-52** ✅ 2026-09-16 — idempotency by constraint, not by `if`: partial unique index
  `(tenant_id, source_key) WHERE source='billing'`, an `idempotency_keys` table behind an `Idempotency-Key` header on
  bulk booking creation, `begin_nested()` + `IntegrityError` → replay or 409, and `UPDATE … WHERE status='pending'`
  + rowcount for review approve/reject. Migration `f5a6b7c8d9e0` de-duplicates first (keeping `MIN(id)`).
  14 tests, each one the race.
- **B-53** ✅ 2026-09-16 — export safety: `= + - @` (and `\t`, `\r`, `\n`) neutralised in xlsx/csv/tsv,
  ISO dates zero-padded, amounts normalised; `=cmd|' /c calc'!A1` is in the tests. 13 tests.

- **B-43** ✅ 2026-09-13 — e-mail export: `EmailStr` single recipient, subject one line ≤ 200 chars, rows ≤ 5000,
  `heavy_limit` on both `/api/export/email*`, every HTML cell `html.escape`d, default SSL context (no `CERT_NONE`),
  SMTP settings read from `Settings`, SMTP errors logged not echoed; compose/.env.example agree on port 465.
- **B-42** ✅ 2026-09-13 — SSRF closed: `ollama_base_url` / `ocr_command` dropped from both update schemas and the
  update path; `resolve_ollama` uses `settings.OLLAMA_BASE_URL` only; responses report the deployment URL;
  AI stream/summary never echo upstream bodies or exception text (logged server-side instead). Tests for PUT/PATCH
  and `resolve_ollama`.
- **B-41** ✅ 2026-09-13 — production compose: `ENVIRONMENT=production` on api + worker, `${SECRET_KEY:?}` /
  `${POSTGRES_PASSWORD:?}`, no `--reload`, two-stage image with `USER app`, `backend/.dockerignore`, worker
  overrides the migrate ENTRYPOINT, db/redis/ollama unpublished, `pg_advisory_xact_lock` in `alembic/env.py`,
  `NEXT_PUBLIC_API_URL` is a build arg the browser can reach, root `.env.example`. **Not built here** — first
  `docker compose up --build` on the Mac is the smoke test.
- **B-50** ✅ 2026-09-13 — one error path in the frontend: the 7 `.response.data.detail` sites use `errorMessage()`;
  dashboard KPI reads `correction_count`; InvoiceCard effect deps fixed. Folds **B-21** — eslint at 0 warnings.
- **B-47** ✅ 2026-09-13 — `schemas/common.py:Money` (finite, ±1e9) on bookings, classify, scanner, export rows;
  `limit=Query(ge=1, le=1000)` on list routes; `round_chf` raises on inf/nan; 422 tests.
- **B-40** ✅ 2026-09-13 — role ladder wired: `require_editor` on every mutating route, `require_admin` on Kontenplan
  replace, classify delete/upload, scanner config, `import?replace=true`. `tests/test_rbac_routes.py` walks the route
  table (a new mutating route without a role check fails CI) + viewer/editor 403 over HTTP.
- **B-70 + B-77** ✅ 2026-09-16 — Jahresabschluss (*Abschluss › Jahr*) and the **one PDF renderer**.
  **B-77 decided: fpdf2** — pure Python, no C build, no wheel theatre in the image; reportlab can do more, but what
  we print is text and tables, and the extra power would have been paid for in installation pain.
  `services/pdf_render.py` is deliberately dumb (A4, one font, title, tables, total rows, footer with page numbers)
  and knows no accounting — which is what makes it usable for every document; Mahnung (B-65), MWST (B-67) and the
  invoice (B-68) can move over when they are next touched.
  **B-70** computes the balance sheet at 31.12. cumulatively from every booking up to that date, the income
  statement from the year only, and proposes depreciation. Two things are deliberate in the code: *without an
  opening balance the balance sheet does not add up* — this system books from the first receipt, nobody typed in
  opening balances, so the difference is shown and explained instead of being sold as the customer's mistake
  (a hint, not a blocker); and the **depreciation rates come from ESTV Merkblatt A/1995** (declining balance:
  furniture 25 %, machines 30 %, office machines/IT/vehicles 40 %, tools 45 %, commercial building 4 %; straight
  line is half). Where the leaflet says nothing — patents on 1700 — there is *no* proposal, only a note.
  `/api/abschluss/jahre · /jahr · /jahr.pdf · /jahr.zip`; the ZIP holds the PDF, the Banana file, the checklist and
  every receipt of the year. No migration. 14 new tests; verified against real Postgres 16 (561).
- **B-69** ✅ 2026-09-16 — E-mail intake (*Rechnungen › E-Mail-Eingang*): one mailbox for the whole deployment, the
  tenant sits in the address (`belege+<slug>@<domain>`, from `EMAIL_INTAKE_DOMAIN`). Two transports, one core:
  `deliver()` takes raw MIME — from the IMAP poll (worker job `email-intake`, registered only when a mailbox is
  configured, plus a manual *Jetzt abrufen*) or from the webhook `POST /api/email/inbound` (404 without a secret, 401
  with a wrong one). Attachments (PDF/image) go through the B-64 ingest, everything else is logged instead of
  swallowed. **Safe by default: an empty allow-list lets nothing through** — the address is guessable, so the first
  mail from a new sender is recorded as *abgelehnt* with the reason and one click puts them on the list (whole
  domains as `@lieferant.ch`). `email_messages` is both receipt and dedup (message-id per tenant), `mail_settings`
  holds the switch and the list. On *Heute*: the card "N neue Belege per E-Mail".
  Migration `e4f5a6b7c8d9`, 21 backend and 4 frontend tests; verified against real Postgres 16 (547).
- **B-68** ✅ 2026-09-15 — Write invoices (*Rechnungen › Rechnung schreiben*): customer + line items produce a QR
  invoice, a debtor booking `1100/3000` on the invoice date (VAT exactly once, with the sales code from the company
  profile) and an open item in direction *ausgang* — so dunning (B-65) and Offene Posten work without a line of
  extra code. `services/swiss_qr.py` writes what `services/qr_bill.py` could only read: QRR (27 digits, recursive
  mod-10) on a QR-IBAN, SCOR (ISO 11649, mod-97) on a normal IBAN, NON without one, plus the SPC payload and the QR
  square as vector SVG with the Swiss cross (segno, now a runtime dependency). The test that matters: the payload
  round-trips through our *own* reader — what a banking app scans parses as a QR bill. New `company_profiles` (who we
  are: address, IBAN, debtor/revenue/bank account, VAT code) and `invoice_positions`; the invoice header stays a
  `Document`. The payment comes back carrying the reference, the Abgleich recognises it as a `referenz` hit and books
  `1020/1100` — one test drives exactly that route. The print view is HTML with the payment part (Empfangsschein +
  Zahlteil, A4); a real PDF arrived later with **B-77**, sending it is **B-79**.
  Migration `d3e4f5a6b7c8`, 19 backend and 6 frontend tests; verified against real Postgres 16.
- **B-67** ✅ 2026-09-15 — MWST-Abrechnung (*Abschluss › Quartal*): Formular 200 aus den Buchungen. Ziffern und
  Reihenfolge nach dem offiziellen ESTV-Formular ab 01.01.2024 (200 · 205 · 220–280 · 289 · 299 · 302/312/342 mit
  Umsatz *und* Steuer · 382 · 399 · 400 · 405 · 410 · 415 · 420 · 479 · 500/510) — beim Bauen gegen das
  Musterformular der ESTV geprüft, nicht aus dem Kopf. Die Seitenzuordnung folgt den Banana-Codes (V… = Umsatz →
  302/312/342, M… = Vorsteuer Material/DL → 400, I… = Vorsteuer Investitionen → 405); fehlt der Code, entscheiden
  die Konten (3… im Haben = Umsatz, 4… im Soll = Material, 5…/6… und Anlagen 15…/16…/17… = Investitionen —
  10…/11… sind kein Aufwand und bleiben ohne Seite, was als Hinweis erscheint). Gutschriften (Erlöskonto im Soll
  oder negativer Umsatz) laufen in Ziffer 235. Ziffern, die kein Buchungssatz hergibt (Bezugsteuer,
  Einlageentsteuerung, Korrekturen, Kürzungen), stehen sichtbar auf 0.00 statt geraten zu werden.
  Saldosteuersatz-Methode: Umsatz × Satz (Satz als Parameter, 0–15 %, die SSS-Ziffer hängt vom Satz ab → 322 ff.),
  ohne Vorsteuer. Plausibilität: drei Blocker (Code ≠ Satz, Code auf der falschen Seite, unbekannter Satz) und drei
  Hinweise (Aufwand ohne Vorsteuer — der 4000er-Fall aus der Roadmap —, Umsatz ohne Satz, Buchung ohne Seite).
  `GET /api/abschluss/quartale`, `GET /api/abschluss/mwst[?quartal=JJJJ-Qn&methode=effektiv|saldo&satz=6.5]` mit
  Tab-getrenntem Kopierblock fürs ePortal und `GET /api/abschluss/mwst.txt` als Blatt für den Treuhänder; echtes PDF
  → B-77. 19 Backend- und 3 Frontend-Tests; gegen echtes Postgres 16 verifiziert (505 passed).
- **B-66** ✅ 2026-09-15 — Monatsabschluss-Check (*Abschluss › Monat*): eine Seite, rot oder grün, nichts zu
  konfigurieren. Die Geldfrage ist die **Bewegung**, nicht der Saldo — was im Monat durch die Bank ging, muss der
  1020-Bewegung der Buchungen entsprechen (`signed_bank_effect`: Bank im Soll = Zufluss, im Haben = Abfluss).
  Ein Saldo-Vergleich bräuchte einen Anfangsbestand, den niemand erfasst hat; die Bewegung braucht nichts und findet
  dieselben Fehler (fehlende Buchung, falsches Konto, doppelt gebucht) — Differenz unter einem Rappen ist Rundung.
  Drei Blocker (Differenz Bank ↔ 1020, nicht abgeglichene Bankzeilen, MwSt-Code ≠ Satz) und vier Hinweise
  (mögliche Doppel, Buchung ohne Beleg mit Verweis auf Art. 958f OR, fällige offene Rechnungen, noch nicht nach
  Banana exportiert); ignorierte Bankzeilen zählen nirgends mit. `GET /api/abschluss/monate` liefert jeden Monat
  mit Daten (der Picker braucht keine Einstellung), `GET /api/abschluss/monat[?monat=JJJJ-MM]` den Bericht mit
  KPIs (Buchungen, Einnahmen, Ausgaben, Bank ↔ 1020) — beide read-only, ein falsches Monatsformat ist ein klarer 400.
  Auf `/dashboard/abschluss` sitzt der Check über dem Export und teilt dessen Prüflisten-Komponente. 15 Backend-
  und 3 Frontend-Tests; gegen echtes Postgres 16 verifiziert (486 passed).
- **B-65** ✅ 2026-09-15 — Offene Posten + Mahnung. `documents` bekommt eine Richtung (migration `c2d3e4f5a6b7`):
  `eingang` = Lieferantenrechnung (Kreditor, wir zahlen), `ausgang` = eigene Rechnung (Debitor, Kunde zahlt) — plus
  `contact_email`, `mahnstufe`, `mahnung_sent_at` und Index `(tenant_id, direction, status)`. `services/offene_posten.py`
  ist rein rechnend: fehlt ein Fälligkeitsdatum, gilt Rechnungsdatum + 30 Tage netto; `days_overdue` /
  `aging_bucket` (nicht fällig · 1–30 · 31–60 · 61–90 · über 90) füllen beide Seiten mit Summen, und `build_items`
  sortiert das Dringendste nach oben. Die Mahnung eskaliert in drei Stufen (Zahlungserinnerung → 1. Mahnung → Letzte
  Mahnung, dort erst der Hinweis auf Verzugszins nach Art. 104 OR), immer mit 10 Tagen Frist, immer als **Entwurf**:
  `GET /api/offene-posten/` (beide Seiten), `GET /{id}/mahnung` (Betreff + Text, nichts gespeichert),
  `GET /{id}/mahnung.html` (druckfertiger A4-Brief, Browser → PDF) und `POST /{id}/mahnung` (`require_editor`) hält
  fest, dass sie raus ist, damit die nächste eskaliert. Verschickt wird nichts von hier; nur ein Ausgang ist mahnbar
  (409 sonst). Auf *Heute*: Karte "Wer schuldet uns / Was schulden wir" mit Summen, Aging-Badges, den dringendsten
  Zeilen und dem Mahnung-Dialog (Text kopieren · Drucken/PDF · als versendet erfassen, Fokus-Falle + Esc). Ein
  echter PDF-Renderer bleibt eine Entscheidung für B-77/B-70. 17 Backend- und 6 Frontend-Tests; gegen echtes
  Postgres 16 verifiziert (471 passed).
- **B-76** ✅ 2026-09-15 — Phase 4 Banana-Stapel: an export is no longer a download but a *Buchungsperiode with a
  status*. `export_batches` (migration `b1c2d3e4f5a6`) records every hand-off — count, total, MwSt total, period,
  filename, sha256 of the rendered file, note — and `bookings.export_batch_id` / `exported_at` stamp what left, so the
  next export offers only what is new and a re-download of an old batch renders byte-identical content (the checksum
  proves it). `services/export_batch.py` first runs a red/green pre-flight in plain German: four blockers (missing
  Soll/Haben, amount 0.00, unreadable date, VAT code that contradicts its rate via `vat_code_for`) and three warnings
  (possible duplicate postings, open bank lines, overdue documents) — warnings never block, a blocker refuses the
  export with 409 and names itself. On export the bookings are stamped, documents whose booking left go to
  `exportiert` (final), and a plain-text Deckblatt (company, period, totals, per-Sollkonto sums, checksum, the exact
  Banana import path) travels with the file. `GET/POST /api/export/batches` + `/preflight`, `/{id}`, `/{id}/file`,
  `/{id}/cover` (`require_editor` on the export itself; viewer may look). `bookings_to_df()` moved into
  `services/export.py` so the router and the batch render the same columns in the same order. `/dashboard/abschluss`
  is the first surface of the target IA: three KPI cards, the checklist, one primary action with an inline
  "Ja, exportieren" confirm, and the batch history with Banana-file and Deckblatt download. 15 backend + 11 frontend
  tests.
- **B-73** ✅ 2026-09-15 — Phase 3 Abgleich. `bank_transactions` keeps every Kontoauszug line (signed amount, value
  date, reference, `dedup_key` so a re-upload counts instead of duplicating) and `matches` links document ↔ line n:1
  with tier/score/reason/part-amount (migration `a1b2c3d4e5f6`). `services/matching.py` is pure: tier 1 QRR/SCOR
  reference = fact (1.0), tier 2 exact amount inside −5/+40 days lifted by vendor-text similarity, tier 3 Sammelauftrag
  (2..5 open invoices summing to the line, lower score and "mehrere Kombinationen möglich" when ambiguous); integer
  Rappen, no document proposed twice, strongest line claims first. `services/abgleich.py` stores proposals and on
  confirm writes one booking per document on the bank line's date with the document's accounts (VAT half-up), sets the
  document `bezahlt` and teaches the vendor → account pairing; reject is remembered, `manual` and `ignore` exist.
  `/dashboard/abgleich`: statement drop zone, KPI cards, proposal cards with the reason sentence, `j/k/a/r`, optimistic
  decisions, open lines with an invoice picker that shows the difference before booking. Shared `lib/format.ts` +
  `lib/inbox-keys.ts`. 42 new tests. Real April statement: 28/28 lines parsed, sums equal the PDF's Umsatztotal.
  Also fixed: the e2e frontend uses `NEXT_DIST_DIR=.next-e2e`, so `make check` no longer collides with `make dev`.
- **B-64** ✅ 2026-09-14 — Phase 1 of the brainstorm: `documents` table (migration `f0a1b2c3d4e5`) — a Rechnung/Beleg with
  file, read facts (vendor, amount, currency, no./dates, QR IBAN + QRR/SCOR reference), proposed Kontierung, status
  offen → bezahlt → exportiert (final) / fehler, booking link. `services/qr_bill.py` decodes the Swiss Payments Code from
  images and PDF pages (zxing-cpp + pypdfium2, QRR mod-10 checked); `services/documents.py`: store → QR (exact) → else
  vision/OCR → classify; a bad file is a `fehler` row. `POST /api/documents/` (≤ 50 files) + list/summary/get/patch/file.
  `/dashboard/rechnungen`: bulk drop zone with progress, KPI cards, status filter, optimistic bezahlt↔offen. 30 tests.
- **B-15** ✅ 2026-09-14 — `/api/scanner/extract` streams SSE when asked (`step` per stage as it happens, then `result`
  / `error` with status + message); JSON otherwise. `ScannerService.extract(on_step=…)` + `extract_events()`.
- **B-14** ✅ 2026-09-14 — review queue: optimistic approve/reject with rollback + toast, `j/k/a/r` (+ arrows) keyboard
  with a visible selection; assistant hotkey moved to `Shift+A`. Page split into hooks/components/helpers (unit-tested).
- **B-49** ✅ 2026-09-14 — off the event loop: `fit_pipeline()` (pure) via `asyncio.to_thread` for train / import /
  worker; scanner status + extract on the providers' async members (one cached Ollama probe); pdfplumber, smtplib and
  the receipt write in threads. `tests/test_event_loop.py` proves a ticker keeps running during training.
- **B-34** ✅ 2026-09-14 — model blobs signed with `HMAC(SECRET_KEY, "model-blob-v1")`; insecure/short SECRET_KEY refuses
  to sign or trust in every environment (train → 503 with the fix); `classifier_models.model_sha256` (migration
  `e8f9a0b1c2d3`) checked on load; `/classify/info.model_trusted` → "Modell neu trainieren" banner. **Retrain once.**
- **B-16** ✅ 2026-09-14 — `hooks/useSystemData.ts`: one SWR key per system endpoint, polled every 60 s; dashboard KPIs,
  SystemChecklist, GettingStarted and the bell share them (4×/3× duplicate requests gone). `buildNotifications()` pure.
- **B-46** ✅ 2026-09-14 — settings save for real: `PATCH /api/auth/me` (display name, any role) and
  `PATCH /api/auth/me/tenant` (company name, admin+); fake notifications/password tabs removed; appearance has no save.
- **B-44** ✅ 2026-09-14 — logout clears every SWR key + the notifications store; `useApi` keys are `[path, userId]`.
- **B-63** ✅ 2026-09-14 — Betrag-Gedächtnis: `training_data.betrag` (migration `d7e8f9a0b1c2`, Banana import fills it);
  `amount_candidate()` classifies a bank line by earlier bookings with the same amount (≥ 2 hits, ≥ 60 % agreeing,
  confidence 0.67 → 0.92), source "Betrag", and carries the tenant's own description ("Cembra Money, Leasing") which the
  Kontoauszug table offers under the bank text. Candidates amount / rules / ML — most confident wins, so a keyword rule
  now beats a hesitant model (the 48 % "revenue" for a 4.00 bank fee). Real UBS April statement × 2024 Banana export:
  8 of 20 counterparty-less E-Banking lines resolved; the rest are Sammelaufträge (n:1 → phase 3 Abgleich).
- **B-48** ✅ 2026-09-13 — `VAT_CODE_BY_RATE` exact map + `vat_code_for()`; the receipt's rate wins, a classifier code
  of the same rate (V81/M81) is kept; amounts > 50'000 are flagged `needs_review` (scanner card shows "Prüfen") instead
  of zeroed.
- **B-45** ✅ 2026-09-13 — Kontoauszug save logs real corrections: `correctionsFor(rows)` sends suggestion as original,
  only for changed rows, `Promise.allSettled` + count in the toast. Unit-tested.
- **B-39** ✅ 2026-09-13 — `TrainingRow` exported; migration `c1d2e3f4a5b6` creates `training_data` (idempotent for
  dev DBs that already have it); PG test: every `Base.metadata` table exists after `upgrade head`.
- **B-30** ✅ 2026-09-11 — `scripts/status.sh` → `STATUS.md` (`make status`): app version, backend/vitest/e2e test
  counts, routers + routes, models, Alembic migrations + head (venv `alembic heads`, else derived from the files),
  open B-xx table folded from ROADMAP.md, done count, date + commit. Pure grep/find, shellcheck-clean;
  `scripts/project-overview.sh` untouched.
- **B-29** ✅ 2026-09-11 — Pre-commit gates completed: `api-types` local hook at pre-push runs
  `scripts/gen-api-types.sh` and fails on `git diff` of `frontend/src/lib/api-types.ts` (same check as the CI
  "api-types" job), triggered by `backend/app/{routers,schemas,models}/**.py`; `eslint` (`npm run lint`) at pre-push
  for `frontend/**.{ts,tsx,css}` — the frontend has no prettier, so eslint is the formatter gate. ruff, gitleaks,
  tsc were already in place.
- **B-37** ✅ 2026-09-11 — Inbound platform events (contracts/events.md, receiver side). `POST /api/platform/events`
  (`routers/platform_events.py`, `services/platform_events.py`): HMAC-SHA256 over `"<ts>.<raw body>"` from
  `X-Platform-Signature: sha256=<hex>` with `PLATFORM_SHARED_SECRET` (constant-time), `X-Platform-Timestamp` ±5 min;
  no Bearer, default per-IP rate limit. `invoice.paid` v1 → one booking `1020 Bank an 1100 Debitoren`, amount from
  the decimal string via `round_chf` (half-up), `datum` = `paid_at` as `DD.MM.YYYY`, text `Zahlung <number> <client>`,
  `source=billing`, `rechnung=<number>`, idempotent on `source_key=billing:invoice:<id>:paid` (202 accepted / 200
  duplicate). 404 secret unset · 401 `bad_signature`/`stale_timestamp` · 400 `unsupported_version`/`unsupported_event`/
  `invalid_payload` · 404 `unknown_tenant` (tid never did SSO — final for billing). `core/errors.py` gained
  `ApiError(status, code, message)` so a route can name its envelope code. 13 tests, signed like billing's sender.
- **B-36** ✅ 2026-09-11 — SSO hand-off + tenant mirroring (contracts/sso.md, ADR-001 amendment, verifier side).
  `POST /api/auth/sso {token}` (`routers/sso.py`, `services/sso.py`): HS256 with `PLATFORM_SHARED_SECRET`,
  `iss=billing`/`aud=buchhaltung`/`type=sso`, `exp-iat ≤ 120 s`, `jti` single-use via `sso_nonces` table (works across
  workers, expired rows purged on the way). 404 secret unset · 401 `sso_invalid`/`sso_expired`/`sso_replayed` · 409
  `email_taken_locally`. Migration `a400bdc46480` (batch ops, PG + SQLite): `tenants.platform_tenant_id` (unique),
  `users.platform_user_id` + `auth_source` (default `local`), unique `(tenant_id, platform_user_id)`, `sso_nonces`.
  First hop creates the tenant from the snapshot (`unique_tenant_slug` + `seed_tenant`) and a shadow user
  (`auth_source=platform`, `password_hash="!platform"`); later hops refresh tenant name/plan/trial and user
  email/name/role. `/api/auth/login` answers 403 `platform_user` for shadow users before checking the password.
  Roles pass through on the shared ladder (unknown → viewer; billing `admin` stays `admin`, no promotion to owner).
  Same email as a local user of the same mirrored tenant → linked (keeps password/role); other tenant → 409.
  Frontend: `/sso` reads `#token=` once (StrictMode-safe), clears the fragment, stores the session like `/login`,
  `router.replace("/dashboard")`, translated error state with a link to `/login`; "Apps" switcher in the top bar
  (`AppSwitcher`, `lib/platform.ts`) links to `NEXT_PUBLIC_BILLING_URL`, hidden when unset. Env: `PLATFORM_SHARED_SECRET`,
  `BILLING_URL`, `NEXT_PUBLIC_BILLING_URL` (.env examples, compose, README "Platform (SSO + events)"). Tests: 18 pytest
  (PG 339 / SQLite 335 passed), Playwright 14 → **17** (`e2e/sso.spec.ts` mints the token with node:crypto).
- **B-19** ✅ 2026-09-11 — a11y pass. Skip link → `<main id="main">` (AppShell, login, register); `hooks/useFocusTrap`
  gives CommandPalette, ShortcutsModal, AssistantPanel and the mobile sidebar Tab-cycling, `Esc` and focus return;
  `<html lang>` follows `getLocale()` (`LangSync`, `setLocale`); every input/select/textarea has a label
  (settings, scanner InvoiceCard `Field` is now a `<label>`, dropzone file inputs, search fields), every table an
  `aria-label`, decorative icons `aria-hidden`. Contrast: light `--muted-foreground`/`--success`/`--warning` are the
  platform tokens mixed 15 % toward `--cd-color-fg` (raw values were 4.1–4.3:1 on the app's tinted chips), `--link`
  = `--cd-color-brand-hover` in dark (brand is 4.2:1 as text), opacity-faded text removed. Found on the way:
  `dark:` utilities never applied — Tailwind 4 defaults to `prefers-color-scheme`, the app toggles `.dark`; fixed
  with `@custom-variant dark`. Gate: `e2e/a11y.spec.ts` (`@axe-core/playwright`) fails on any serious/critical
  violation on login, dashboard, scanner, modell, settings in light **and** dark, plus skip-link and focus-trap
  checks. Playwright 3 → **11**. Advisory (moderate) left open: heading-order on `modell`, duplicate landmark on
  `settings`.
- **B-18** ✅ 2026-09-11 — Every dashboard page has skeleton / empty / error. Shared `components/shared/`
  `EmptyState` (existing) · `ErrorState` (envelope `error.message` + request id via `lib/errors.ts`, retry =
  SWR `mutate` or the hook's `load`) · `PageSkeleton` (header/metrics/rows; `dashboard/loading.tsx` uses it).
  Copy is in `lib/i18n.ts` (DE + EN; FR falls back to DE). `review`, `audit`, `kontenplan`, `lernverlauf` moved
  to SWR so retry is a `mutate()`; `kontenplan`, `lernverlauf`, `kontoauszug`, `scanner` split into
  `hooks/ components/ types.ts` (B-10 rule, every page ≤ 120 lines). `alert()` is gone. vitest 58 → **65**
  (`states.test.tsx`, jsdom for the three components only).

  | Page | Before (loading · empty · error) | After |
  |---|---|---|
  | `dashboard` | metric skeletons · `GettingStarted` · none — cards showed "–" | skeletons · same · inline `ErrorState`, retry re-fetches both keys |
  | `review` | "Laden…" spinner · `EmptyState` without action · swallowed (looked empty) | `PageSkeleton` · `EmptyState` + "Rechnung scannen" · `ErrorState` + `mutate`; approve/reject failures toast the envelope |
  | `audit` | one `MetricCardSkeleton` · `EmptyState` · red sentence, no retry | `PageSkeleton` · `EmptyState` + action · `ErrorState` + `mutate`; table has `aria-label` |
  | `kontenplan` | none · none (blank table) · none (unhandled rejection) | `PageSkeleton` · `EmptyState` (+ "Keine Konten gefunden" for a filtered list) · `ErrorState` + retry; save/train report the envelope |
  | `lernverlauf` | whole page spinner · per-tab `EmptyState` (charts: none) · none (unhandled rejection) | `PageSkeleton` · translated `EmptyState` per tab + action, charts included · `ErrorState` + retry |
  | `kontoauszug` | processing card · drop zone · `alert()` with raw `detail` | same · drop zone (keyboard-operable) · `ErrorState` with "Erneut versuchen" (same file) or "Andere Datei"; save/export failures toast the envelope |
  | `scanner` | `StatusBar` skeleton · `DropZone` · toast only | same · same · inline `ErrorState` per failed file with retry; envelope message instead of raw `detail` |
  | `modell` | spinner · none (only the status badge) · toast, then a blank page | `PageSkeleton` · `EmptyState` "Noch kein Modell trainiert" + train action · `ErrorState` + retry |
  | `insights` | spinner in `ResultsTable` · "Keine Treffer" (search only) · none (silently empty) | `PageSkeleton` · `EmptyState` "Noch keine Buchungen" + "Kontoauszug hochladen" · `ErrorState` + retry |
  | `settings` | none ("–" placeholders) · n/a · swallowed | `PageSkeleton` in the tab body · n/a · `ErrorState` + retry; save failures toast |
- **B-35** ✅ 2026-09-10 — Scanner-config first-call race: the dashboard fires several `/api/scanner/*` calls at
  once and every one tried to insert the tenant's `scanner_configs` row. `get_or_create` now tolerates the lost
  `IntegrityError` and re-reads the winner (83bb0b2, `ScannerService`), and the review-threshold service wraps its
  insert in a savepoint so a lost race cannot poison the request session (c1c2b01, `services/scanner_config.py`).
  Both paths regression-tested in `test_scanner_pipeline.py`.
- **B-13** ✅ 2026-09-10 — `GET /api/health` → `{status, version, database, migration_head, storage, worker}`:
  `database` ok/error (status `degraded` on error), `migration_head` = revision applied in the DB (null on a
  create_all schema), `storage` = backend name, `worker` = `in-api` | `separate`. `ENVIRONMENT=production` trims
  the body to `status` + `version`. Tests 303 → **307** (PG).
- **B-10** ✅ 2026-09-10 — `settings/page.tsx` 352 → 66 and `insights/page.tsx` 320 → 53 lines, split into
  `hooks/ components/ helpers.ts types.ts` like `modell/`; largest new file 82 lines. No markup or copy change;
  the e2e Insights step still finds the search input and table.
- **B-09** ✅ 2026-09-10 — Every upload to `/api/scanner/extract` and `/api/pdf/parse` is written through
  `services/storage.py` as `receipts/<tenant_id>/<uuid>.<ext>` *before* extraction (`services/receipts.py`) and
  returned as `source_key`. Migration `55e64308d75f` adds nullable `bookings.source_key`; `POST /api/bookings/`
  accepts it only for the caller's own tenant (400), `GET /api/bookings/{id}/source` streams the file (404
  cross-tenant, keyless, or vanished — isolation suite). Kontoauszug passes the key through on save. Tests run
  LocalStorage under `tmp_path` (autouse fixture). Tests 290 → **303** (PG).
- **B-08** ✅ 2026-09-10 — `python -m app.worker` is a real entrypoint (loops, `--once`); the API lifespan starts
  the same jobs in-process only with `RUN_WORKER_IN_API=true` (default). The training queue moved from process
  memory to `training_jobs` (migration `52eb7a4363f0`): `log_correction` enqueues in the request session, the
  worker claims by conditional update, dedups per tenant, hands a job back on shutdown. Compose: `worker` service
  (same image, restart unless-stopped, waits for the api healthcheck), api runs `RUN_WORKER_IN_API=false`.
  Found on the way: the B-04 migration test used `downgrade -1`, which broke as soon as a newer migration
  existed — now targets its base revision. Tests 282 → **290** (PG; 279 → 287 SQLite).
- **B-33** ✅ 2026-09-10 — Playwright happy path against the real API: `playwright.config.ts` starts uvicorn on
  8100 with a throw-away SQLite DB + the frontend with `NEXT_PUBLIC_API_URL`; `e2e/happy-path.spec.ts` registers,
  opens Kontenplan, books via the API with the UI's token, finds the row in Insights, exports CSV. CI frontend job
  installs the backend for the server. Note: there is no manual booking form in the UI.
- **B-11** ✅ 2026-09-10 — vitest (`npm run test`, in CI and `make test`): 58 tests for `lib/errors.ts`,
  `modell/helpers.ts`, `lib/booking-analytics.ts`. Pure helpers only; pages stay on Playwright.
- **B-32** ✅ 2026-09-10 — bandit `-ll` blocking. `defusedxml` for uploaded Banana XML; every Ollama `httpx` call has
  a settings timeout (`OLLAMA_TIMEOUT` 60 s, `OLLAMA_VISION_TIMEOUT` 120 s, `OLLAMA_PROBE_TIMEOUT` 10 s). Found on the
  way: `POST /api/classify/upload` stored any `.pkl` that `_load_model()` later unpickled (RCE for a logged-in user).
  Model blobs are now HMAC-SHA256 signed with `SECRET_KEY` (`services/model_blob.py`); unsigned blobs are rejected on
  upload and ignored on load (retrain once). No schema change; sha256 column → B-34. Tests 253 → **277** (SQLite).
- **B-04** ✅ 2026-09-10 — `preprocess()` strips month tokens as whole words (`\b`, optional trailing dot; `"mr"` →
  `"mär|mrz"`). Data migration `4c7e2a91b0d3` re-derives every `memory.lookup_key` (source text recovered from the
  tenant's latest matching `corrections` row, else the new function on the stored key), collapses duplicates to the
  highest id, reversible with the frozen legacy function inside the migration. Postgres migration test seeds a collision.
- **B-05** ✅ 2026-09-10 — `calc_mwst`, the credit shortcut and the AI-context money fields go through `round_chf()`
  (half-up). Matrix: 0.125 / 0.135 / 2.675 at 8.1 % and 2.6 %, negative amounts and rates. Tests 233 → **254** (PG).
- **B-12** ✅ 2026-09-10 — `.github/workflows/security.yml`: gitleaks, pip-audit (blocking, ecdsa/HS256 ignore),
  npm audit high with registry-retry, Trivy on the backend image, bandit/semgrep advisory. npm audit fix bumped
  5 transitive dev deps; both audits clean. Bandit mediums → B-32.
- **B-07** ✅ 2026-09-10 — Rate-limit keys `tenant:<tid>` (Bearer decoded without DB) / `ip:<addr>`. `RATE_LIMIT_DEFAULT`
  200/min on every route, `RATE_LIMIT_CLASSIFY` 60/min on `classify/{,predict,batch}`, `RATE_LIMIT_HEAVY` 30/min on
  `scanner/extract`, `pdf/parse`, `ai/{chat,summary}`, `classify/train`. Found and fixed: slowapi's middleware never
  matched a route on FastAPI ≥ 0.135 (nested routers), so the default limit was silently off — now an app-level
  dependency. 429 uses the error envelope (`rate_limited`) + `Retry-After`. Tests 216 → **233**.
- **B-06** ✅ 2026-09-10 — `POST /api/export/{banana,csv,excel}` and `/api/export/email/rows` require a login
  (same `get_current_user` dependency as everything else); anonymous → 401 covered in the isolation guard.
- **B-26** ✅ 2026-09-10 — Tenant columns → platform contract: `plan` → `subscription_plan` (rename, data kept),
  `slug` (unique, derived from name, suffix on collision), `trial_ends_at`, `is_active` (403 `Tenant deaktiviert`).
  Migration `921d958b8530` verified up/down/up; API image now runs `alembic upgrade head` on start;
  platform `--cd-*` tokens imported (1.6). Tests 203 → **216**.
- **B-31** ✅ 2026-09-10 — Platform auth contract: token `{sub,tid,role,type,jti}`, `tid`/`type` verified, legacy `tenant_id` accepted one release, `require_role()` ladder (owner›admin›editor›viewer). Tests 193 → **203**.
- **B-01** ✅ 2026-09-09 — **fix(export)**: `fmt_swiss` lost the carry (`1234.999 → 1'234.00`), amounts used
  half-even. New `round_chf()` (Decimal, `ROUND_HALF_UP`). 13 regression cases.
- **B-02** ✅ 2026-09-09 — Tests 6 → **193** (+2 skipped): factories, tenant isolation for every router,
  Banana/CSV/Excel export, classifier layers, storage.
- **B-03** ✅ 2026-09-09 — `modell/page.tsx` 955 → 20 files, largest 107 lines. tsc + lint green.
- **B-00** ✅ 2026-09-09 — `services/storage.py`: `StorageBackend` (local | s3), env-driven, `model_storage.py`
  routed through it. Note: no receipt upload path existed → B-09.

---

## Phase progress (mirrors chadev-platform/ROADMAP.md)

| Phase | Status |
|---|---|
| 0 Recon | ✅ |
| 0.5 Risk fixes before platform work | ✅ B-00…B-03 (branch `feat/phase0-risks`) |
| 1 Platform contract | 1.2 ✅ B-31 · 1.4 ✅ B-26 · 1.6 ✅ tokens imported |
| 2 Security | ✅ B-06, B-07, B-32, B-34, B-40, B-41, B-42, B-43 · open: B-24 (ADR-002), B-25, B-54, B-55 |
| 3 Reliability | ✅ B-04, B-05, B-08, B-11, B-33, B-35, B-39, B-47, B-48, B-49, B-63, B-64, B-73, B-76, B-51, B-52 · open: B-56, B-57 |
| 4 Polish | ✅ B-09, B-13, B-66, B-67, B-76, B-53 · open: B-22, B-61 |
| 5 UX | ✅ B-14, B-15, B-16, B-18, B-19, B-44, B-45, B-46, B-50 (+B-21), B-65, B-58, B-59, B-71 · open: B-17, B-20 |
| 6 Together | ✅ B-36 (SSO + mirroring), B-37 (events) · deploy: `docs/DEPLOY-CHECKLIST-B36-B37.md` · parked: B-38 |
| 7 DX | ✅ B-12, B-29, B-30 · open: B-60, B-62 |
