import { describe, expect, it } from "vitest";
import {
  bucketRows,
  mahnungHistory,
  mahnungLabel,
  overdueLabel,
  overdueTone,
  urgentItems,
  type OpenItemOut,
  type SideOut,
} from "./offene-posten";

const item = (over: { id?: number; mahnstufe?: number; sent?: string | null; days?: number }): OpenItemOut =>
  ({
    document: {
      id: over.id ?? 1,
      mahnstufe: over.mahnstufe ?? 0,
      mahnung_sent_at: over.sent ?? null,
    },
    due_date: "2026-09-01",
    days_overdue: over.days ?? 0,
    bucket: "1_30",
    mahnbar: true,
  }) as unknown as OpenItemOut;

describe("overdueLabel / overdueTone", () => {
  it("says it in words, singular included", () => {
    expect(overdueLabel(0)).toBe("Noch nicht fällig");
    expect(overdueLabel(1)).toBe("1 Tag überfällig");
    expect(overdueLabel(47)).toBe("47 Tage überfällig");
  });
  it("turns red only after the first month", () => {
    expect(overdueTone(0)).toBe("success");
    expect(overdueTone(30)).toBe("warning");
    expect(overdueTone(31)).toBe("danger");
  });
});

describe("mahnungLabel", () => {
  it("names the stage that would go out next and stops at the last", () => {
    expect(mahnungLabel(0)).toBe("Zahlungserinnerung");
    expect(mahnungLabel(1)).toBe("1. Mahnung");
    expect(mahnungLabel(2)).toBe("Letzte Mahnung");
    expect(mahnungLabel(3)).toBe("Letzte Mahnung");
  });
});

describe("mahnungHistory", () => {
  it("is empty before the first Mahnung and dated afterwards", () => {
    expect(mahnungHistory(item({}))).toBe("");
    expect(mahnungHistory(item({ mahnstufe: 2, sent: "2026-09-01T10:00:00Z" }))).toContain("1. Mahnung am");
    expect(mahnungHistory(item({ mahnstufe: 1, sent: null }))).toBe("Zahlungserinnerung");
  });
});

describe("urgentItems", () => {
  it("keeps the backend order and caps the list", () => {
    const side = { items: [item({ id: 1 }), item({ id: 2 }), item({ id: 3 })] } as unknown as SideOut;
    expect(urgentItems(side, 2).map((i) => i.document.id)).toEqual([1, 2]);
    expect(urgentItems(undefined)).toEqual([]);
  });
});

describe("bucketRows", () => {
  it("drops empty buckets and keeps the aging order", () => {
    const side = { buckets: { nicht_faellig: 0, "1_30": 500, ueber_90: 250 } } as unknown as SideOut;
    expect(bucketRows(side)).toEqual([
      { key: "1_30", label: "1–30 Tage", amount: 500 },
      { key: "ueber_90", label: "Über 90 Tage", amount: 250 },
    ]);
    expect(bucketRows(undefined)).toEqual([]);
  });
});
