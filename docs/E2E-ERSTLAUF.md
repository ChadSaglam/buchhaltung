# The first end-to-end run

Roadmap NEXT, item 2. Every check so far has been a test suite, and a test suite
only asks the questions somebody thought to write down. This is the run that asks
the rest: one pass through the product **as a user**, not as its author.

Rules for the run:

- **Do not fix anything while running.** Write the line down and keep going. A run
  that stops at the first bug finds one bug; a run that finishes finds the shape.
- **Write down what you expected, not only what happened.** "Abgleich proposed
  nothing" is a bug report nobody can act on a week later. "I expected the 47.30
  Migros line to match the Migros receipt from the 3rd; it proposed nothing" is.
- **Use real paper.** A generated sample proves the renderer works. It does not
  prove the OCR reads *your* suppliers' invoices.

## 0 — Before

- [ ] The Postgres password has been **changed** (not just removed from `setup.sh`).
- [ ] `docker compose down` — nothing holding :3000 — then the stack is up:
      `docker compose up -d --wait db redis api worker web`
- [ ] Database is **empty**. The point is to be tenant #1 from nothing.

## 1 — Onboarding · registration

- [ ] Register at `/register`. Note anything you had to guess.
- [ ] `/dashboard` (Heute): does the checklist tell a new user what to do first,
      or does it assume knowledge you have and a customer does not?
- [ ] Kontenplan: import a real chart of accounts through the B-20 wizard.
      Check the preview's "disappears" list against what you expected.

## 2 — Belege

- [ ] `/dashboard/belege/scanner` — upload **a real Swiss QR invoice**. Exact read?
- [ ] Upload **a receipt with no QR code** (till receipt, foreign invoice).
      Record: vendor, amount, VAT code, proposed accounts — each right or wrong.
- [ ] Correct one wrong classification. Then upload a second invoice from the
      *same vendor*: did it learn? This is the loop the whole product is sold on.

## 3 — Bank

- [ ] `/dashboard/bank` — upload a **real** camt/PDF statement.
      Line count parsed vs. line count on the paper. Umsatztotal vs. the PDF's.
- [ ] `/dashboard/bank/abgleich` — walk the proposals with `j/k/a/r`.
      Count: tier 1 (reference), tier 2 (amount), tier 3 (Sammelauftrag), and
      **how many were wrong**. A wrong confident match is worse than no match.
- [ ] Leave at least one line unmatched on purpose and see what Heute says.

## 4 — Abschluss

- [ ] `/dashboard/abschluss` — month check. Does the Bank ↔ 1020 difference
      come out at 0.00? If not, is the message enough to find out why?
- [ ] VAT quarter (form 200). Compare **against a quarter you actually filed**.
- [ ] Export batch → `pack.zip`. Open it. Would a Treuhänder accept it cold?

## 5 — RLS, the check that needs data

`docs/RUNBOOK-RLS-CUTOVER.md` section 4. On an empty database it passes for the
wrong reason: RLS fails as an *empty list*, not an error. Now that rows exist:

- [ ] Count rows as the owner role and as `app_rw` with the tenant context set.
      Same number = the policies are letting the app through.
- [ ] Register a **second** tenant, put one booking in it, and confirm tenant 1
      cannot see it. That is the assertion the product is sold on.

## Output

One list of findings, each one a sentence. Items that are code go to the roadmap
with a B-number. Items that are *the product being confusing* are the more
valuable half — and they are the half no test suite was ever going to produce.
