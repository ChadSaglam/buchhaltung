# Brainstorm — where buchhaltung goes after phases 0.5–7 (2026-09-12)

> Thinking-partner notes, not a spec. Positions are deliberate; argue with them.

## Frame

The north star says "more dynamic · professional · easier to improve · together · user-friendly". Phases 0.5–7 delivered
the plumbing (tests, migrations, SSO, events, states, a11y). The review found the product's two promises are currently
**unproven in the code itself**:

- "It learns from you" — the Kontoauszug path never logs a correction (B-45), the scanner path collapses VAT rates (B-48),
  and one customer's supplier names are hard-coded into every tenant's rules (B-56).
- "Hand it to your Treuhänder" — the export pack (B-17) is still LATER, exports are formula-injectable (B-53), and there is
  no audit trail in the UI (B-22).

So the question is not "what feature next" but **"which promise do we make true first?"**

## Provocations

1. **Who pays — the SME or the Treuhänder?** Everything in NOW/NEXT assumes the SME reviews bookings themselves
   (review queue, keyboard shortcuts, KPI refresh). Swiss micro-SMEs mostly *don't* — they hand a shoebox to a Treuhänder
   who bills by the hour. If the Treuhänder is the buyer, the hero screen is the **export pack + audit trail**, and the
   review queue is *their* tool (P-02 client portal stops being parked).
2. **"More dynamic" may be the wrong north-star column.** Optimistic accept/reject (B-14) shaves 300 ms off an action a
   user does a few times a week. A wrong VAT code (B-48) costs a real Rappen amount on every hotel receipt, forever.
   Correctness beats latency for bookkeeping; "professional" should outrank "dynamic".
3. **The learning loop has no feedback to the user.** Even when corrections *are* logged, nothing says "the model now
   books Migros to 4000 automatically". Without a visible win, users stop correcting — and then the model stops
   improving. Lernverlauf exists but is a stats page, not a moment.
4. **Usage limits (B-23) are the real gate to revenue.** Billing R-106 (Stripe) is next on the platform roadmap; a paid
   plan means nothing if free tenants can scan unlimited receipts and store unbounded files (B-54 found no quota at all).
5. **Feature-parity trap to name:** Abacus export (P-01), mobile PWA (P-03), AI chat. None of these change whether a
   Treuhänder accepts the Banana file on the first try.

## Ideas that survived

| Idea | Why it is interesting | Riskiest assumption |
|---|---|---|
| **A. "Treuhänder-ready" as the hero flow** — one click: Banana TSV + PDF summary + receipts zip + audit log (B-17 + B-22), formula-safe, with a "checked by AI, 3 items need you" cover page | Turns the export into the product's proof of value; the artefact is what the buyer *touches* | That Treuhänder accept a machine-produced pack without re-keying it |
| **B. "It learned" moments** — after each correction: toast "Nächstes Mal: Migros → 4000 automatisch"; weekly digest of auto-booked lines; confidence shown as *why* (memory / rule / model) not a percentage | Makes the loop visible; drives the corrections the model needs; cheap (the data exists in `corrections`, `memory`) | That users care enough to correct if they see payoff |
| **C. Plan-gated usage from day one** — meter scans/receipts/exports via `usage_event`, soft limit banner, hard limit at 2× | Makes Stripe meaningful; also closes the unmetered-storage hole (B-54) | That the free tier is generous enough not to kill activation |
| D. Review queue as inbox (B-14 done right) — j/k/a/r, batch approve, "why" per item | Daily-loop polish | Only valuable once A/B make people open the queue |
| E. Treuhänder portal (P-02) — read-only tenant view via SSO role `viewer` | The role ladder (B-40) makes this nearly free | That Treuhänder want yet another login |

## Position

**Strongest direction: A + B together**, in that order, before B-14/B-16. A makes "professional" true; B makes
"self-learning" true. Both need the correctness fixes from the review first (B-45, B-48, B-53, B-56) — those are not
tech debt, they are the feature. C rides along with B-54 and should land before Stripe goes live in billing.

**Riskiest assumption:** that a Treuhänder will accept the pack as-is. Test it before building the PDF cover: export a
real month for one tenant, hand the Banana file + receipts zip to two Treuhänder, ask what they re-key.

**Suggested next step (≤ 2 h):** two 20-minute calls with Treuhänder who already receive Banana files from clients.
Questions: what do you re-key, what do you reject, what would make you *recommend* the tool to clients.

**Parked:** Abacus (P-01) until a Treuhänder asks; PWA (P-03) until the review queue is the daily surface; AI chat
improvements — keep, but it is not on the path to revenue.
