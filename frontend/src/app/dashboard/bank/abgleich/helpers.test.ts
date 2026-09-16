import { describe, expect, it } from "vitest";

import { differenceHint, documentTotal, isCertain, selectedTotal } from "./helpers";
import type { AbgleichItem, DocumentOut } from "./types";

const doc = (id: number, amount: number | null): DocumentOut =>
  ({ id, amount, status: "offen", vendor: `V${id}` }) as DocumentOut;

const item = (tier: string, amounts: number[]): AbgleichItem =>
  ({
    tier,
    score: 1,
    reason: "",
    is_split: amounts.length > 1,
    transaction: { id: 1, amount: -amounts.reduce((a, b) => a + b, 0) },
    documents: amounts.map((a, i) => ({ document: doc(i + 1, a), match_id: i + 1, amount: a })),
  }) as AbgleichItem;

describe("Abgleich helpers (phase 3)", () => {
  it("treats a reference hit as certain, everything else as a judgement", () => {
    expect(isCertain(item("referenz", [10]))).toBe(true);
    expect(isCertain(item("betrag_datum", [10]))).toBe(false);
    expect(isCertain(item("sammelauftrag", [6, 4]))).toBe(false);
  });

  it("sums the documents of a bundle without float drift", () => {
    expect(documentTotal(item("sammelauftrag", [0.1, 0.2, 0.3]))).toBe(0.6);
    expect(documentTotal(item("sammelauftrag", [87.55, 924.45]))).toBe(1012);
  });

  it("sums only the ticked invoices", () => {
    const docs = [doc(1, 60), doc(2, 40), doc(3, null)];
    expect(selectedTotal(docs, new Set([1, 2]))).toBe(100);
    expect(selectedTotal(docs, new Set([3]))).toBe(0);
    expect(selectedTotal(docs, new Set())).toBe(0);
  });

  it("says plainly whether a manual selection adds up", () => {
    expect(differenceHint(-100, 100)).toEqual({ ok: true, text: "Summe stimmt genau" });
    expect(differenceHint(-100, 0).ok).toBe(false);
    expect(differenceHint(-100, 120)).toEqual({ ok: false, text: "CHF 20.00 mehr als die Bankzeile" });
    expect(differenceHint(-100, 90)).toEqual({ ok: false, text: "CHF 10.00 weniger als die Bankzeile" });
  });
});
