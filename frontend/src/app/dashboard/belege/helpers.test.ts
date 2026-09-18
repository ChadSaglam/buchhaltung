import { describe, expect, it } from "vitest";

import { formatCHF, formatDate, isOverdue, sortDocuments } from "./helpers";
import type { DocumentOut } from "./types";

const doc = (over: Partial<DocumentOut>): DocumentOut =>
  ({
    id: 1, kind: "rechnung", status: "offen", filename: "", vendor: "", amount: null, currency: "CHF",
    invoice_no: "", invoice_date: null, due_date: null, qr_iban: "", qr_reference: "", qr_message: "",
    extraction_source: "qr", extraction_confidence: 1, kt_soll: "", kt_haben: "", mwst_code: "", mwst_pct: "",
    classification_confidence: 0, booking_id: null, error: "", created_at: null, updated_at: null,
    ...over,
  }) as DocumentOut;

describe("Rechnungen helpers (phase 1)", () => {
  it("formats Swiss money and dates", () => {
    expect(formatCHF(1949.45)).toBe("CHF 1'949.45");
    expect(formatCHF(1234567.5)).toBe("CHF 1'234'567.50");
    expect(formatCHF(-3)).toBe("CHF -3.00");
    expect(formatCHF(null)).toBe("–");
    expect(formatDate("2026-04-12")).toBe("12.04.2026");
    expect(formatDate(null)).toBe("–");
  });

  it("overdue = open and due before today", () => {
    const today = new Date("2026-09-14T10:00:00");
    expect(isOverdue(doc({ due_date: "2026-09-13" }), today)).toBe(true);
    expect(isOverdue(doc({ due_date: "2026-09-14" }), today)).toBe(false);
    expect(isOverdue(doc({ due_date: "2026-09-01", status: "bezahlt" }), today)).toBe(false);
    expect(isOverdue(doc({}), today)).toBe(false);
  });

  it("sorts errors first, open by due date, then newest", () => {
    const sorted = sortDocuments([
      doc({ id: 1, status: "bezahlt" }),
      doc({ id: 2, status: "offen", due_date: "2026-10-01" }),
      doc({ id: 3, status: "fehler" }),
      doc({ id: 4, status: "offen", due_date: "2026-09-01" }),
      doc({ id: 5, status: "offen" }),
      doc({ id: 6, status: "bezahlt" }),
    ]);
    expect(sorted.map((d) => d.id)).toEqual([3, 4, 2, 5, 6, 1]);
  });
});

// --- B-89: a till receipt paid by card is not an open payable -----------------

describe("isOverdue — bereits an der Kasse bezahlt", () => {
  const laengstFaellig = { status: "offen", due_date: "2020-01-01" } as Partial<DocumentOut>;

  it("an unpaid invoice past its due date is overdue", () => {
    expect(isOverdue(doc(laengstFaellig))).toBe(true);
  });

  it("the Landi receipt is not — the money left at the till on 7 November", () => {
    expect(isOverdue(doc({ ...laengstFaellig, paid_at_source: true }))).toBe(false);
  });

  it("paid_at_source wins even while status is still offen for the Abgleich", () => {
    // `offen` here means "not yet matched to a bank line", which stays true.
    expect(isOverdue(doc({ status: "offen", due_date: "2020-01-01", paid_at_source: true }))).toBe(false);
  });
});
