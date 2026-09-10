import { describe, expect, it } from "vitest";

import {
  accuracyBarClass,
  accuracyTextClass,
  downloadFilename,
  fileExtension,
  filterMemory,
  formatDate,
  IMPORT_EXTENSIONS,
  isOverfit,
} from "./helpers";
import type { MemoryEntry } from "./types";

describe("accuracy classes", () => {
  it.each([
    [0.85, "bg-success", "text-success"],
    [0.99, "bg-success", "text-success"],
    [0.6, "bg-warning", "text-warning"],
    [0.849, "bg-warning", "text-warning"],
    [0.59, "bg-destructive", "text-destructive"],
    [0, "bg-destructive", "text-destructive"],
  ])("%f → %s / %s", (acc, bar, text) => {
    expect(accuracyBarClass(acc)).toBe(bar);
    expect(accuracyTextClass(acc)).toBe(text);
  });
});

describe("formatDate", () => {
  it("shows a dash for an empty value", () => {
    expect(formatDate("")).toBe("—");
  });

  it("renders Swiss day.month.year with time", () => {
    // Local time; use noon to stay clear of any timezone day rollover.
    const local = new Date(2026, 2, 5, 12, 7);
    expect(formatDate(local.toISOString())).toBe("05.03.2026, 12:07");
  });
});

describe("fileExtension", () => {
  it.each([
    ["export.XLSX", ".xlsx"],
    ["a.b.csv", ".csv"],
    ["noext", "noext"],
  ])("%s → %s", (name, ext) => {
    expect(fileExtension(name)).toBe(ext);
  });

  it("matches the accepted import extensions", () => {
    for (const ext of IMPORT_EXTENSIONS) expect(fileExtension(`Banana${ext.toUpperCase()}`)).toBe(ext);
  });
});

describe("downloadFilename", () => {
  const now = new Date(Date.UTC(2026, 8, 10, 14, 5, 59));

  it.each([
    ["bundle", "buchhaltung_bundle_20260910T1405.zip"],
    ["model", "buchhaltung_model_20260910T1405.pkl"],
    ["memory", "buchhaltung_memory_20260910T1405.json"],
  ] as const)("%s → %s", (type, expected) => {
    expect(downloadFilename(type, now)).toBe(expected);
  });
});

describe("filterMemory", () => {
  const entries: MemoryEntry[] = [
    { lookup_key: "swisscom rechnung", beschreibung: "", kt_soll: "6500", kt_haben: "1020", mwst_code: "", mwst_pct: 0 },
    { lookup_key: "migros filiale", beschreibung: "", kt_soll: "6500", kt_haben: "1020", mwst_code: "", mwst_pct: 0 },
    { lookup_key: null as unknown as string, beschreibung: "", kt_soll: "6500", kt_haben: "1020", mwst_code: "", mwst_pct: 0 },
  ];

  it("returns everything for an empty filter", () => {
    expect(filterMemory(entries, "")).toHaveLength(3);
  });

  it("matches case-insensitively on the key and tolerates a missing key", () => {
    expect(filterMemory(entries, "SWISS").map((e) => e.lookup_key)).toEqual(["swisscom rechnung"]);
    expect(filterMemory(entries, "nothing")).toEqual([]);
  });
});

describe("isOverfit", () => {
  it("flags a train/validation gap above 15 points", () => {
    expect(isOverfit(0.95, 0.7)).toBe(true);
    expect(isOverfit(0.9, 0.8)).toBe(false);
  });

  it("never flags when either accuracy is unknown (0)", () => {
    expect(isOverfit(0, 0.5)).toBe(false);
    expect(isOverfit(0.9, 0)).toBe(false);
  });
});
