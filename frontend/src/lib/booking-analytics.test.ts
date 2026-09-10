import { describe, expect, it } from "vitest";

import type { Booking } from "@/lib/api";
import { detectAnomalies, monthlyStats, parseQuery, searchBookings } from "./booking-analytics";

let nextId = 1;
function booking(overrides: Partial<Booking>): Booking {
  return {
    id: nextId++,
    datum: "15.03.2026",
    beschreibung: "Testbuchung",
    betrag: -100,
    kt_soll: "6500",
    kt_haben: "1020",
    mwst_code: "",
    mwst_pct: "",
    mwst_amount: 0,
    source: "test",
    ...overrides,
  };
}

describe("parseQuery", () => {
  it("extracts direction, amount bound, month, year and residual text", () => {
    const q = parseQuery("Ausgaben über CHF 1'500 im März 2026 Swisscom");
    expect(q).toEqual({ text: "swisscom", direction: "debit", minAmount: 1500, month: 3, year: 2026 });
  });

  it("reads Swiss and German number formats", () => {
    expect(parseQuery("unter 1'234.50").maxAmount).toBe(1234.5);
    expect(parseQuery("weniger als 1.234,50").maxAmount).toBe(1234.5);
    expect(parseQuery("mehr als 99,9").minAmount).toBe(99.9);
  });

  it("takes an explicit account and does not mistake a year or an amount for one", () => {
    expect(parseQuery("konto 6500").konto).toBe("6500");
    expect(parseQuery("Miete 2026").konto).toBeUndefined();
    expect(parseQuery("über 4400").konto).toBeUndefined();
    expect(parseQuery("Rechnung 4400 Beratung").konto).toBe("4400");
  });

  it("recognises credit wording and month abbreviations", () => {
    const q = parseQuery("Einnahmen Sept.");
    expect(q.direction).toBe("credit");
    expect(q.month).toBe(9);
  });

  it("drops stopwords and numbers from the residual text", () => {
    expect(parseQuery("die Buchungen von der Migros mit 3 Artikeln").text).toBe("migros artikeln");
  });
});

describe("searchBookings", () => {
  const rows = [
    booking({ id: 1, datum: "05.03.2026", beschreibung: "Swisscom Rechnung", betrag: -89.9, kt_soll: "6500" }),
    booking({ id: 2, datum: "2026-04-01", beschreibung: "Kunde Zahlung", betrag: 2500, kt_soll: "1020", kt_haben: "3000" }),
    booking({ id: 3, datum: "20/04/2026", beschreibung: "Beratung Treuhand", betrag: -1800, kt_soll: "4400" }),
    booking({ id: 4, datum: "kein datum", beschreibung: "Unbekannt", betrag: -10 }),
  ];
  const ids = (list: Booking[]) => list.map((b) => b.id);

  it("filters by month across all supported date formats and excludes undated rows", () => {
    expect(ids(searchBookings(rows, { text: "", month: 4 }))).toEqual([2, 3]);
    expect(ids(searchBookings(rows, { text: "", year: 2026 }))).toEqual([1, 2, 3]);
  });

  it("filters by absolute amount bounds", () => {
    expect(ids(searchBookings(rows, { text: "", minAmount: 1000 }))).toEqual([2, 3]);
    expect(ids(searchBookings(rows, { text: "", maxAmount: 50 }))).toEqual([4]);
  });

  it("matches an account on either side and a direction on the sign", () => {
    expect(ids(searchBookings(rows, { text: "", konto: "3000" }))).toEqual([2]);
    expect(ids(searchBookings(rows, { text: "", direction: "credit" }))).toEqual([2]);
    expect(ids(searchBookings(rows, { text: "", direction: "debit" }))).toEqual([1, 3, 4]);
  });

  it("requires every free-text term to appear in description or accounts", () => {
    expect(ids(searchBookings(rows, { text: "beratung 4400" }))).toEqual([3]);
    expect(ids(searchBookings(rows, { text: "beratung 6500" }))).toEqual([]);
  });

  it("composes parseQuery and searchBookings end to end", () => {
    expect(ids(searchBookings(rows, parseQuery("Ausgaben über 1000 im April")))).toEqual([3]);
  });
});

describe("monthlyStats", () => {
  it("aggregates per YYYY-MM, newest first, with debit/credit split", () => {
    const stats = monthlyStats([
      booking({ datum: "03.01.2026", betrag: -100, kt_soll: "6500" }),
      booking({ datum: "2026-01-20", betrag: 300, kt_soll: "1020" }),
      booking({ datum: "10.02.2026", betrag: -50.5, kt_soll: "6500" }),
      booking({ datum: "nope", betrag: -999 }),
    ]);
    expect(stats.map((s) => s.month)).toEqual(["2026-02", "2026-01"]);
    expect(stats[1]).toEqual({
      month: "2026-01",
      count: 2,
      totalDebit: 100,
      totalCredit: 300,
      net: 200,
      byAccount: { "6500": 100, "1020": 300 },
    });
    expect(stats[0].totalDebit).toBe(50.5);
  });

  it("returns an empty list for no bookings", () => {
    expect(monthlyStats([])).toEqual([]);
  });
});

describe("detectAnomalies", () => {
  it("flags a strong amount outlier as high and sorts it first", () => {
    const rows = [
      // A single outlier can only reach z >= 3 with enough baseline rows ((n-1)/sqrt(n) >= 3).
      ...Array.from({ length: 15 }, (_, i) => booking({ id: 10 + i, betrag: -100 - i, datum: `${10 + i}.05.2026` })),
      booking({ id: 99, betrag: -5000, datum: "31.05.2026" }),
    ];
    const anomalies = detectAnomalies(rows);
    expect(anomalies[0].booking.id).toBe(99);
    expect(anomalies[0].severity).toBe("high");
    expect(anomalies[0].reason).toContain("5000.00");
  });

  it("flags a missing account assignment and a duplicate", () => {
    const rows = [
      booking({ id: 1, kt_soll: "", kt_haben: "", betrag: -10 }),
      // Duplicate key = date + |amount| + first 12 characters of the description.
      booking({ id: 2, datum: "01.06.2026", beschreibung: "Coop Zürich Filiale", betrag: -42 }),
      booking({ id: 3, datum: "01.06.2026", beschreibung: "COOP ZÜRICH Filiale Nr. 2", betrag: 42 }),
    ];
    const reasons = Object.fromEntries(detectAnomalies(rows).map((a) => [a.booking.id, a.reason]));
    expect(reasons[1]).toMatch(/Kontierung/);
    expect(reasons[3]).toMatch(/Dublette/);
    expect(reasons[2]).toBeUndefined();
  });

  it("skips the statistical check below four amounts and reports one entry per booking", () => {
    const rows = [booking({ id: 1, betrag: -1 }), booking({ id: 2, betrag: -100000, kt_soll: "", kt_haben: "" })];
    const anomalies = detectAnomalies(rows);
    expect(anomalies).toHaveLength(1);
    expect(anomalies[0].booking.id).toBe(2);
    expect(anomalies[0].reason).toMatch(/Kontierung/);
  });
});
