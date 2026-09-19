import { describe, expect, it } from "vitest";
import {
  batchSubtitle,
  checkCountLabel,
  checkTone,
  differenceText,
  exportLabel,
  formatPeriod,
  monthLabel,
  isEmptyZiffer,
  methodeLabel,
  monthVerdict,
  mwstVerdict,
  sortChecks,
} from "./helpers";
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

describe("monthVerdict", () => {
  it("blockers win over hints, and clean says so", () => {
    expect(monthVerdict(2, 3)).toEqual({ tone: "danger", text: "2 Punkte blockieren den Abschluss" });
    expect(monthVerdict(1, 0).text).toBe("1 Punkt blockieren den Abschluss");
    expect(monthVerdict(0, 1)).toEqual({ tone: "warning", text: "Abschluss möglich · 1 Hinweis" });
    expect(monthVerdict(0, 4).text).toBe("Abschluss möglich · 4 Hinweise");
    expect(monthVerdict(0, 0)).toEqual({ tone: "success", text: "Monat ist sauber abgeschlossen" });
  });
});

describe("differenceText", () => {
  it("names the direction, and rounding is not a difference", () => {
    expect(differenceText(0)).toBe("Bank und Konto 1020 stimmen");
    expect(differenceText(0.001)).toBe("Bank und Konto 1020 stimmen");
    expect(differenceText(-40)).toBe("CHF 40.00 mehr gebucht als auf der Bank");
    expect(differenceText(40)).toBe("CHF 40.00 mehr auf der Bank als gebucht");
  });
});

describe("monthLabel", () => {
  it("falls back to the key when no label came with it", () => {
    expect(monthLabel("2026-04", { "2026-04": "April 2026" })).toBe("April 2026");
    expect(monthLabel("2026-05", {})).toBe("2026-05");
  });
});

describe("mwstVerdict", () => {
  it("says pay, get back, or nothing", () => {
    expect(mwstVerdict(593, 0)).toEqual({ tone: "danger", text: "CHF 593.00 zu bezahlen" });
    expect(mwstVerdict(0, 324)).toEqual({ tone: "success", text: "CHF 324.00 Guthaben" });
    expect(mwstVerdict(0, 0)).toEqual({ tone: "neutral", text: "Nichts zu bezahlen" });
  });
});

describe("isEmptyZiffer", () => {
  it("is empty only when both sides are zero or absent", () => {
    expect(isEmptyZiffer({ umsatz: 0, steuer: 0 })).toBe(true);
    expect(isEmptyZiffer({ umsatz: null, steuer: null })).toBe(true);
    expect(isEmptyZiffer({ umsatz: 0, steuer: 81 })).toBe(false);
    expect(isEmptyZiffer({ umsatz: 1000, steuer: null })).toBe(false);
  });
});

describe("methodeLabel", () => {
  it("names the method and the rate when there is one", () => {
    expect(methodeLabel("effektiv", null)).toBe("Effektive Methode");
    expect(methodeLabel("saldo", 6.5)).toBe("Saldosteuersatz 6.5 %");
    expect(methodeLabel("saldo", null)).toBe("Saldosteuersatz");
  });
});
