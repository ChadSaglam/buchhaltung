# ADR-003: how a standing order becomes an Abgleich proposal (B-74 part B)

**Status:** Proposed — needs a decision from the owner before any code is written
**Date:** 2026-09-16
**Deciders:** Chad (owner)
**Related:** B-74 part A (Dauerbuchungen on Heute), B-73 (Abgleich), B-52 (idempotency by constraint)

## The question in one paragraph

B-74 part A recognises recurring payments from the booking history and says which one is missing this month
(`services/dauerbuchungen.py`). Part B is the other half: when an unmatched bank line *is* the Cembra instalment,
Abgleich should propose it. The detection for that already exists — `dauerbuchungen.passende()` returns the one
standing order a line of that amount and date can be, and `None` rather than a guess when it is ambiguous. What
does not exist is a place to put the proposal. Every proposal in Abgleich today is a `Match` row, and a `Match`
points at a `Document`. A standing order has no document — that is the whole reason it needs recognising.

This was left out of part A on purpose. It is not a typing change.

## Why `document_id` cannot simply become nullable

`Match.document_id` is `NOT NULL` and four separate things depend on it:

1. **`uq_matches_pair`** — `UNIQUE (tenant_id, document_id, transaction_id)` (`models/match.py:37`). In Postgres
   two NULLs are *distinct*, so the moment `document_id` is nullable the constraint stops constraining anything
   for standing orders. Re-running the engine — which B-52 made safe by leaning on exactly this index — would
   insert a second, third, fourth proposal for the same bank line.
2. **`_decided_pairs()`** (`services/abgleich.py:137`) returns `set[tuple[document_id, transaction_id]]` and is
   how a rejected proposal stays rejected. With a NULL on the left, every standing-order decision on one
   transaction collapses to the same key: reject one and you reject all of them, forever.
3. **`confirm()`** (`services/abgleich.py:243-284`) is a money path. It loads the document and reads seven fields
   off it — `kt_soll`, `kt_haben`, `mwst_code`, `mwst_pct`, `vendor`, `invoice_no`, `file_key` — then writes two
   back (`status = bezahlt`, `booking_id`). None of the seven has an analogue on a standing order, and the two
   writes have nothing to write to.
4. **The learning.** The last thing `confirm()` does is `save_to_memory(doc.vendor, doc.kt_soll, …)`. The whole
   point of `Match` per its own docstring is that "every human decision here is a training row for the match
   scorer". A standing order's identity is its normalised `schluessel`, not a vendor.

So "make the column nullable" is really "add a second branch through the confirmation of money", plus a rewritten
uniqueness rule, plus a widened dedup key. That is a redesign, and it is the kind that looks like a one-line diff
in the model file.

## The three options

**A — nullable `document_id` with a discriminator.** Add `kind` (`dokument` | `dauerbuchung`) and `dauer_key`,
replace `uq_matches_pair` with two *partial* unique indexes (one `WHERE document_id IS NOT NULL`, one on
`(tenant_id, dauer_key, transaction_id) WHERE dauer_key IS NOT NULL`), widen `_decided_pairs()` to key on
`(kind, document_id or dauer_key, transaction_id)`, and split `confirm()`'s loop body in two.
*Cost:* one migration, four edits inside the money path, and every existing `Match` test now has to prove the
document branch still behaves. *Gain:* one inbox, one status machine, one place the user decides.

**B — a separate `StandingProposal` table.** Its own row, its own status/decided_by/decided_at, joined into the
same Abgleich list at the service layer. *Cost:* duplicated status machinery and a second thing to keep in sync
with the UI; the "one transaction settles several things" case (Sammelauftrag) would have to work across two
tables. *Gain:* the money path for documents is not touched at all.

**C — no proposal row; book it directly.** The Abgleich screen offers the unmatched line a button — "book as
Dauerbuchung: Cembra 770.60" — which creates a `Booking` with `source="dauerbuchung"` and sets the transaction to
`gebucht`. Nothing is stored between proposing and booking, because there is nothing to decide later: the user is
looking at the line when they answer.
*Cost:* a rejected suggestion is not remembered, so the same line keeps being offered until it is booked or
manually cleared. No training row. *Gain:* no migration, no change to `Match`, no second branch in `confirm()`.

## Recommendation

**C first, A later if the memory turns out to matter.** The argument for A is the training row, and today there is
no scorer being trained on standing orders — `passende()` is a deterministic amount-and-day rule, not a model. A
`Match` row for it would be bookkeeping about bookkeeping. The argument against C is that a wrong suggestion is
offered again tomorrow; with `passende()` returning `None` on anything ambiguous, the rate of wrong suggestions
should be near zero, and if it is not, that is the signal that A is worth its migration.

The thing I would not do is A *quietly*. If it is A, the partial indexes and the split `confirm()` deserve their
own change with its own tests, not a rider on a UI feature.

## What I need from the owner

1. Is a rejected standing-order suggestion something the system must remember? (Yes → A. No → C.)
2. Should a standing order ever be part of a Sammelauftrag — one transfer settling an invoice *and* a standing
   order at once? (Yes → A, because C cannot express it.)
3. Does a confirmed standing order have to leave an audit trail distinct from the booking it creates? (B-22 logs
   the booking either way; this asks whether the *proposal* is also an audited object.)
