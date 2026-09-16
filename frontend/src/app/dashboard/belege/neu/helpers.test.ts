import { describe, expect, it } from "vitest";
import { chf, fehlendeAngaben, num, totals, zeilenbetrag } from "./helpers";
import { LEERE_POSITION } from "./types";

describe("chf", () => {
  it("groups thousands the Swiss way", () => {
    expect(chf(1234.5)).toBe("1'234.50");
    expect(chf(0)).toBe("0.00");
    expect(chf(-42)).toBe("-42.00");
  });
});

describe("num", () => {
  it("reads what people type", () => {
    expect(num("1'234.50")).toBe(1234.5);
    expect(num("1234,50")).toBe(1234.5);
    expect(num(" 12 ")).toBe(12);
    expect(num("")).toBe(0);
    expect(num("abc")).toBe(0);
  });
});

describe("totals", () => {
  const rows = [
    { ...LEERE_POSITION, bezeichnung: "Beratung", menge: "4", einzelpreis: "150" },
    { ...LEERE_POSITION, bezeichnung: "Spesen", menge: "1", einzelpreis: "40" },
  ];

  it("adds VAT on top of net prices", () => {
    expect(totals(rows, "-8.10")).toEqual({ netto: 640, mwst: 51.84, total: 691.84, satz: 8.1 });
  });

  it("leaves the total alone without a rate", () => {
    expect(totals(rows, "")).toEqual({ netto: 640, mwst: 0, total: 640, satz: 0 });
  });

  it("counts a line as quantity times unit price", () => {
    expect(zeilenbetrag({ ...LEERE_POSITION, menge: "2.5", einzelpreis: "10.20" })).toBe(25.5);
  });
});

describe("fehlendeAngaben", () => {
  it("names what is missing", () => {
    expect(fehlendeAngaben({ name: "" }, [LEERE_POSITION])).toEqual([
      "Kundenname",
      "mindestens eine Position mit Betrag",
    ]);
    expect(
      fehlendeAngaben({ name: "Muster AG" }, [{ ...LEERE_POSITION, bezeichnung: "Beratung", einzelpreis: "100" }]),
    ).toEqual([]);
  });
});
