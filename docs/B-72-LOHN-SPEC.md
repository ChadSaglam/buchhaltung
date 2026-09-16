# B-72 Lohn light — spec and sourced groundwork (2026-09-16)

> **Status (2026-09-16): built as option B, with the shape option C needs.** The owner chose C. What shipped is
> the skeleton C sits on — the models, the engine, the payslip, the booking and the Jahreszusammenzug — with every
> rate as per-tenant configuration and nothing guessed. The four things that make it C are listed under
> "What is still missing for option C" below; each of them is data or a certification, not code.
>
> The document is kept as written: the reasoning for refusing it first, and the sourced figures, are the reason the
> implementation looks the way it does.

## Why this one was refused when the rest of the NEXT block was built

Every other item in the 2026-09-16 night run had the same safety property: if the code is wrong, a test fails or a
number on screen looks odd, and the owner notices before anything leaves the building. Payroll does not have it.

1. **A wrong deduction is the customer's liability, not a display bug.** Too little AHV withheld and the employer
   owes the difference plus interest; too much and the employee was underpaid. Neither surfaces until the
   Ausgleichskasse reconciles the year.
2. **The rates change every January** and are set by several different bodies (AHV/IV/EO federally, ALV by SECO,
   BVG by the BSV, UVG by the insurer, FAK and Quellensteuer per canton). A hard-coded table is wrong within a year
   and wrong silently.
3. **The roadmap already says so**: "High liability — after B-65…B-70, and validated against a real Treuhänder run."
   That validation has not happened. Building it first inverts the order the roadmap chose on purpose.
4. **Most of the value is not in the arithmetic.** The arithmetic is a morning. The Lohnausweis layout, the
   Sozialversicherungs-Jahresmeldung format, Quellensteuer tariffs per canton and the ELM/Swissdec transmission are
   the work — and Swissdec certification is a project of its own.

Nothing here says "never". It says: decide deliberately, and decide what *kind* of feature it is first.

## The decision to make before any code

**Which of these is B-72?**

| Option | What it is | Effort | Liability |
|---|---|---|---|
| **A — Lohnjournal only** | Record the payslips the customer's existing payroll produces, so the bookings and the year-end figures are right. No rates in our code. | `S` / `M` | none |
| **B — Calculator with owner-entered rates** | We compute deductions, but every rate is a field the owner (or their Treuhänder) fills in, with the published value shown as a reference, never as a default. Same pattern as B-71's `gewinnsteuer_satz`. | `M` / `M` | low |
| **C — Full payroll** | We own the rates, the Quellensteuer tariffs, the Lohnausweis and the Jahresmeldung; ideally Swissdec-certified. | `H` / `L` | high |

The B-71 precedent argues for **B**, and B is a superset of A. C is a product decision, not a sprint.

## Reference figures (valid 2026 — check every January, do not hard-code without a review date)

Collected 2026-09-16. Each line names its source; anything not in this table is not known and must not be guessed.

### AHV / IV / EO
- Total **10.6 %** of the AHV wage — AHV 8.7 %, IV 1.4 %, EO 0.5 %.
- Split in half: **5.3 % employee, 5.3 % employer**. No ceiling.
- People past retirement age pay AHV/IV/EO but **no ALV**.
- There is also an administration-cost surcharge (Verwaltungskostenbeitrag), which each Ausgleichskasse sets
  itself — so it is a per-tenant field, not a constant.
- Source: [ahv-iv.ch, Merkblatt 2.01 "Lohnbeiträge an die AHV, die IV und die EO"](https://www.ahv-iv.ch/p/2.01.d)

### ALV
- **2.2 %** of the insured earnings, **1.1 % each**.
- Ceiling **CHF 148 200** per year. Since 1 January 2023 there is **no** solidarity contribution above it.
- Note: the fact sheet fetched on 2026-09-16 still states the figures as of 1 January 2025. Confirm the 2026
  values with SECO or the Ausgleichskasse before using them.
- Source: [ahv-iv.ch, Merkblatt 2.08](https://www.ahv-iv.ch/p/2.08.d)

### BVG (mandatory part)
- Eintrittsschwelle **CHF 22 680** · Koordinationsabzug **CHF 26 460** · oberer Grenzbetrag **CHF 90 720**
- coordinated salary: min **CHF 3 780**, max **CHF 64 260**
- minimum interest rate **1.25 %**, legal minimum conversion rate at 65 **6.80 %**
- Altersgutschriften are age-banded and the actual contribution comes from the **pension fund's own regulations**,
  not from the BVG minimum — so this is per-tenant configuration, never a constant in our code.
- Source: [BVG-Eckwerte (BSV figures)](https://www.schwiizerfranke.com/bvg-eckwerte)

### UVG, FAK, Quellensteuer — deliberately not tabulated
- **UVG/UVGZ**: the rate is in the contract with the insurer, per tenant. BU is the employer's; NBU is usually the
  employee's. There is no national number to look up.
- **FAK (Familienzulagen)**: cantonal, employer-only, varies by Ausgleichskasse.
- **Quellensteuer**: a tariff *table* per canton, reissued yearly, with tariff codes per marital status, children
  and church tax. This is the single biggest reason option C is a project: it is a data-maintenance commitment, not
  a formula.

## If it is option B, the shape that fits this codebase

```
backend/app/models/lohn_settings.py     one row per tenant: every rate above as a nullable column,
                                        plus the Ausgleichskasse's admin surcharge and the UVG/BVG rates
                                        from the customer's own contracts. Null = not set = no calculation,
                                        the B-71 pattern.
backend/app/models/mitarbeiter.py       employee: name, AHV number, birth date, entry/exit, pensum, monthly
                                        gross, children, canton, Quellensteuer yes/no.
backend/app/models/lohnabrechnung.py    one payslip per employee per month, storing the rates that were used
                                        (never recomputing history when a rate changes).
backend/app/services/lohn.py            pure: gross → each deduction → net, plus the employer's side.
                                        Every deduction carries the rate and the base it was computed on, so
                                        the payslip can show its own arithmetic.
backend/app/services/lohn_pdf.py        payslip PDF via services/pdf_render.py (B-77 already exists).
```

Booking (KMU Kontenrahmen): gross to **5000** Lohnaufwand, employee deductions to **2270** Sozialversicherungen,
net to **1020** Bank; the employer's share to **5700** Sozialversicherungsaufwand against 2270.

Rules worth writing down before the first line of code:

1. **A payslip is immutable once issued.** Corrections are a new payslip, never an edit — the same reason B-52
   exists.
2. **Store the rate on the payslip.** A January rate change must not silently rewrite December.
3. **Every rate field says where its number came from and when it was last checked**, on screen, like B-71's
   `GEWINNSTEUER_QUELLE` and B-70's `ESTV_QUELLE`.
4. **Refuse rather than guess.** No rate hinterlegt → no payslip, with a sentence saying which field is missing.
   Never a plausible default.
5. **A "Nicht für die Einreichung" watermark** on the payslip until a Treuhänder has signed off one real month.

## What to do first, when you get to it

Not code: take one real payslip the customer's current provider produced, and reproduce it by hand with the figures
above. If the net matches to the rappen, option B is a week. If it does not, the gap tells you exactly which
per-tenant field is missing — and that list is the actual spec.

**This is still the next step, and the code enforces it.** Every payslip is printed with a *"Nicht für die
Einreichung"* watermark until `lohn_settings.freigegeben` is set, and that flag has its own endpoint
(`POST /api/lohn/settings/freigabe`) so it cannot be set by accident while editing a percentage. It is false for
every tenant and no migration sets it: the sign-off is a statement that a person did the comparison above, and
nothing in this app can make that statement on their behalf.

## What shipped (2026-09-16)

Exactly the layout this document proposed, plus the two guards it asked for:

| File | What it does |
|---|---|
| `backend/app/models/lohn_settings.py` | one row per tenant; AHV/ALV defaulted (federal), UVG/UVGZ/KTG/FAK/Verwaltungskosten nullable, plus `freigegeben` |
| `backend/app/models/mitarbeiter.py` | employee; BVG as a **franc amount** per month, Quellensteuer as a **rate**, both from documents we do not produce |
| `backend/app/models/lohnabrechnung.py` | one payslip per employee per month, storing the rate next to every amount |
| `backend/app/services/lohn.py` | pure gross→net; raises `LohnKonfigurationFehlt` naming every missing rate at once |
| `backend/app/services/lohn_service.py` | year-to-date gross for the ALV ceiling, issuing, and the three bookings |
| `backend/app/services/lohn_pdf.py` | payslip and Jahreszusammenzug via `pdf_render.py` |
| `frontend/src/app/dashboard/lohn/` | the page; `src/lib/lohn.ts` holds the pure parts |

Two places Swiss payroll is not obvious, both pinned down by tests: the payroll month is 30 days regardless of the
calendar, and the ALV ceiling is cumulative over the year rather than a monthly twelfth.

The five rules above are all in the code. Rule 3 is `LOHN_QUELLE` in `models/lohn_settings.py`, shown above the rate
form. Rule 4 is `LohnKonfigurationFehlt` → `ApiError(400, "lohn_konfiguration_fehlt", …)`, which is a code the
frontend can branch on to send the user to the settings rather than a bare 400.

## What is still missing for option C

None of it is arithmetic; all of it is data or a certification.

1. **Quellensteuer tariff tables** — per canton, per Tarifcode, reissued yearly. Today the *rate* is a field on the
   employee, filled in from the cantonal tariff by whoever knows it. Owning the tables is a maintenance commitment.
2. **BVG Altersgutschriften** — the fund's own regulations decide the amount. Today it is a franc amount per
   employee, copied from the fund's statement, which is the number that actually gets paid.
3. **Lohnausweis (Formular 11)** — prescribed layout with numbered boxes and a barcode. What ships is a
   *Jahreszusammenzug* that says on the page that it is not one.
4. **Swissdec ELM** — the yearly Sozialversicherungs-Jahresmeldung transmission. A certification, not a file
   format.

---
_Sources: [ahv-iv.ch Merkblatt 2.01](https://www.ahv-iv.ch/p/2.01.d) · [ahv-iv.ch Merkblatt 2.08](https://www.ahv-iv.ch/p/2.08.d) · [BVG-Eckwerte](https://www.schwiizerfranke.com/bvg-eckwerte)_
