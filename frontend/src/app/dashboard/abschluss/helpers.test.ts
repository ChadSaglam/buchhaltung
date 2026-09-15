import { describe, expect, it } from "vitest";
import { batchSubtitle, checkCountLabel, checkTone, exportLabel, formatPeriod, sortChecks } from "./helpers";
import type { ExportCheck } from "./types";

const check = (over: Partial<ExportCheck>): ExportCheck => ({
  code: "c",
  label: "l",
  detail: "d",
  severity: "blocker",
  count: 0,
  booking_ids: [],
  ...over,
});

describe("checkTone", () => {
  it("is green while the count is zero, whatever the severity", () => {
    expect(checkTone(check({ severity: "blocker" }))).toBe("success");
    expect(checkTone(check({ severity: "warnung" }))).toBe("success");
  });
  it("separates a blocker from a warning", () => {
    expect(checkTone(check({ severity: "blocker", count: 2 }))).toBe("danger");
    expect(checkTone(check({ severity: "warnung", count: 2 }))).toBe("warning");
  });
});

describe("checkCountLabel", () => {
  it("says nothing when green and uses the singular for one", () => {
    expect(checkCountLabel(check({}))).toBe("");
    expect(checkCountLabel(check({ count: 1 }))).toBe("1 Buchung");
    expect(checkCountLabel(check({ count: 4 }))).toBe("4 Buchungen");
  });
});

describe("sortChecks", () => {
  it("puts blockers first, warnings next, green last", () => {
    const rows = [
      check({ code: "green" }),
      check({ code: "warn", severity: "warnung", count: 1 }),
      check({ code: "block", count: 1 }),
    ];
    expect(sortChecks(rows).map((c) => c.code)).toEqual(["block", "warn", "green"]);
  });
});

describe("formatPeriod", () => {
  it("collapses one day and shows a range otherwise", () => {
    expect(formatPeriod(null, null)).toBe("–");
    expect(formatPeriod("2026-04-05", "2026-04-05")).toBe("05.04.2026");
    expect(formatPeriod("2026-04-01", "2026-04-30")).toBe("01.04.2026 – 30.04.2026");
  });
});

describe("exportLabel", () => {
  it("names the consequence", () => {
    expect(exportLabel(0, true)).toBe("Nichts zu exportieren");
    expect(exportLabel(3, false)).toBe("Zuerst die roten Punkte korrigieren");
    expect(exportLabel(1, true)).toBe("1 Buchung nach Banana exportieren");
    expect(exportLabel(28, true)).toBe("28 Buchungen nach Banana exportieren");
  });
});

describe("batchSubtitle", () => {
  it("reads as one line", () => {
    expect(batchSubtitle(2, 1234.5)).toBe("2 Buchungen · CHF 1'234.50");
  });
});
