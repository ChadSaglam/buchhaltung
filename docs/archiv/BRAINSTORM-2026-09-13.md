# Brainstorm — from "scan & export" to "documents in, Banana out" (2026-09-13)

> Thinking-partner notes, deliberately opinionated. Short on purpose. Argue with the positions.
> Builds on `docs/BRAINSTORM-2026-09-12.md` (Treuhänder-ready pack, "it learned" moments) — this one is about the **core loop** the owner described:
> own model → Rechnungen (single + bulk) → Kontoauszug → match → push to Banana → model keeps learning.

## 1. Frame — what exists vs. what was asked

| Owner's step | Today in the repo | Gap |
|---|---|---|
| Own, improvable model | Per-tenant TF-IDF + LogReg (`services/classifier.py`), corrections + memory tables, training worker | Only classifies *accounts*. The Kontoauszug path never logs a correction (B-45) → loop is dead there. No model for extraction or matching. |
| Rechnungen, single + bulk | `/api/scanner/extract` — **one** file per call, result goes straight to review queue / booking | No `Rechnung` entity. No bulk. No "this invoice is still unpaid" state. |
| Kontoauszug | `/api/pdf/parse` → rows classified in memory → saved as bookings | No `Kontoauszug`/`BankTransaction` entity. PDF only (lossy). |
| Match invoice ↔ bank line | — | Does not exist. Bookings are flat rows; nothing links a receipt to a payment. |
| Push to Banana | `df_to_banana_tsv` → download | Export is a file, not a push. Nothing remembers *what has already been sent*. |

**The real shift:** today the product is a *classifier with an export button*. The vision is a **document-centric ledger**: documents in → payments in → reconciled → posted. That is a data-model change first, a model change second, a UI change third.

## 2. Diverge — ideas on the table

1. **Three small learners, not one big model.** (a) account classifier (exists), (b) field extractor confidence/repair (vendor → account, VAT rate → code), (c) match scorer (invoice ↔ bank line). Each is tiny, per-tenant, retrained nightly from human decisions. "Own model" = the *data flywheel*, not an LLM.
2. **Every human click is a training row.** Approve / correct / confirm-match / reject-match all write to `corrections` (or a new `decisions` table). No separate "train the model" button that nobody presses. Nightly retrain + "Nächstes Mal automatisch" toast (idea B from 09-12).
3. **Swiss QR-bill first.** Most CH invoices since 2022 carry a QR code with amount, IBAN, 27-digit reference, payee. Decoding the QR is *exact*; OCR/vision becomes the fallback. Cheap (`pyzbar`/`zxing-cpp`), massive precision win, and the reference is the perfect matching key.
4. **camt.053 XML instead of PDF for Kontoauszug.** Every Swiss bank exports camt.053; it carries amount, value date, counterparty, and the QR/ESR reference. PDF parsing stays as fallback. Matching drops from "fuzzy" to "lookup" for anything with a reference.
5. **Matching engine = rules first, model second.** Tier 1: reference number exact. Tier 2: amount exact + date window ± 30d + vendor similarity (`vendor_similarity.py` exists). Tier 3: partial / n:1 (one payment, several invoices; Skonto). Tier 4: model scores the leftovers. Show *why* matched, never a bare percentage.
6. **Bulk intake = drag 50 PDFs *or* email-in.** A per-tenant inbox address (`belege+<slug>@…`) is how SMEs actually "bulk upload": they forward supplier mails. Drag-and-drop is the demo; email-in is the habit.
7. **One hero screen: "Abgleich" (reconciliation inbox).** Left: open invoices. Right: unmatched bank lines. Middle: proposals with reason. Keyboard: `j/k`, `a` accept, `r` reject, `m` manual. Replaces "review queue" as the daily surface.
8. **"Push to Banana" = a *Buchungsperiode* with status.** Postings get `exported_at` + `export_batch_id`. Export = "everything reconciled and not yet exported". Re-export never duplicates. This is what "when everything is OK" means in code.
9. **Idempotent Banana hand-off, two levels.** Level 1 (now): Banana-import TSV per batch + receipts zip + cover sheet (idea A from 09-12). Level 2 (verify first): a Banana *extension* (JS) that pulls the batch from our API — **unverified whether Banana extensions may call HTTP**. 30-minute check, not a plan item until checked.
10. **Cross-tenant priors, tenant-private data.** Vendor → account mapping (Migros → 4000, Swisscom → 6510) is the same for most SMEs. Ship a global prior, let tenant corrections override. Fixes B-56 (hard-coded customer names in rules) for real.

## 3. Provoke — the uncomfortable questions

- **"Own model" for what, exactly?** Training a vision/LLM model in-house is a year of work for worse results than Kimi/Qwen via Ollama. The defensible "own" part is the per-tenant decision history + match scorer + priors. Say that out loud so the roadmap doesn't chase the wrong thing.
- **Who uploads 200 invoices?** If the answer is "the Treuhänder at year-end", the hero is bulk + export pack. If it is "the owner weekly", the hero is email-in + Abgleich inbox. The product can't be great at both on day one.
- **PDF Kontoauszug is a trap.** 189 lines of `pdf_parser.py` for every bank layout, forever. camt.053 is one parser for all banks. Keep PDF as fallback, stop investing in it.
- **Matching without a reference is guessing.** Push users toward QR-bills / references *in the UI* ("3 invoices have no reference — matched by amount+date, please confirm"). Honesty beats a confident wrong match.
- **"More dynamic" still tempts.** Optimistic UI everywhere is polish. A wrong match posted to Banana is a *real* Rappen error. Correctness first (same position as 09-12).
- **Banana "push" may not exist.** If Banana extensions can't fetch, the best possible product is "one click → import file that Banana accepts on the first try". That is still excellent. Don't promise a push before the 30-minute check.

## 4. Converge — strongest direction

**Build the document-centric ledger + rule-based Abgleich, then let the learners ride on top.**

Why: it makes all five owner steps true with the smallest model risk. Rules + QR + camt.053 get ~80% of matches *exactly*; the model only has to be good on the residual, and the residual is what humans confirm — which is exactly the training data the model needs.

### Data model (the whole change in one glance)

```
Document (Rechnung/Beleg)      BankTransaction (from camt.053 / PDF)
  tenant_id, kind, file_key      tenant_id, statement_id, value_date,
  vendor, amount, currency,      amount, counterparty, reference,
  invoice_no, qr_reference,      raw
  due_date, status
        └──────── Match (document_id, transaction_id, score, reason, decided_by, status) ────────┘
                                   │
                              Posting (today's Booking + match_id, exported_at, export_batch_id)
```

### Phases (each one shippable, each one closes a loop)

| Phase | Ships | Proves |
|---|---|---|
| **0 · make the loop honest** | B-39, B-45, B-48, B-40 from ROADMAP; every Kontoauszug edit logs a correction | "It learns" is true on both paths |
| **1 · Rechnungen** | `Document` model + bulk upload (N files, one job) + QR-bill decode + open-invoice list with status | Invoices are *things*, not rows |
| **2 · Kontoauszug** | `BankTransaction` + camt.053 import (PDF fallback) + statement list | Bank lines are *things* |
| **3 · Abgleich** | `Match` + rule engine tiers 1–3 + the Abgleich inbox screen + every decision → training row | Matching, with reasons |
| **4 · Banana batch** | `export_batch` + "alles OK → exportieren" + idempotent re-export + cover sheet; Banana-extension check done | "Push" is real (file or extension) |
| **5 · learners** | Match scorer trained on phase-3 decisions; nightly retrain; "gelernt" toasts + weekly digest | The model visibly improves |

### Riskiest assumption
That users can *get* camt.053 and QR-bill invoices. If most tenants only have PDFs and paper, phases 1–2 lean on vision/OCR and match quality drops to "amount + date" — still workable, but the model has to carry more, earlier.

### Suggested next step (≤ 2 h)
1. Grab **one real month** from one tenant: the bank's camt.053 export + the invoices for that month.
2. Run a 30-line script: decode QR references, match on reference then amount+date window. Count exact / fuzzy / unmatched.
3. That number decides whether phase 5 is urgent or optional — and it is the demo for the Treuhänder calls from the 09-12 brainstorm.

## 5. Parked
- In-house vision/LLM training — no; keep Ollama models, own the *decision data*.
- Abacus / other targets — after Banana batch export is idempotent.
- Mobile PWA — after Abgleich is the daily surface.
- OmniRoute in the backend — useful once the LLM calls are behind one `LLM_BASE_URL`; not on the critical path (see `docs/TOOLING.md`).
