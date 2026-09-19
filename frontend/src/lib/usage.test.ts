import { describe, expect, it } from "vitest";
import type { UsageCounter } from "@/lib/api-schema";
import { istUnbegrenzt, naechsterReset, periodeText, prozent, ton, verbrauchText, warnungen } from "@/lib/usage";

function z(over: Partial<UsageCounter> = {}): UsageCounter {
  return {
    key: "belege",
    label: "Belege pro Monat",
    benutzt: 10,
    limit: 100,
    anteil: 0.1,
    warnung: false,
    erreicht: false,
    periode: "monat",
    ...over,
  } as UsageCounter;
}

describe("istUnbegrenzt", () => {
  it("is true only when the limit is null", () => {
    expect(istUnbegrenzt(z({ limit: null }))).toBe(true);
    expect(istUnbegrenzt(z({ limit: 0 }))).toBe(false);
    expect(istUnbegrenzt(z())).toBe(false);
  });
});

describe("prozent", () => {
  it("rounds the share to whole percent", () => {
    expect(prozent(z({ anteil: 0.123 }))).toBe(12);
  });

  it("never exceeds 100, even if the backend reports more", () => {
    expect(prozent(z({ anteil: 4 }))).toBe(100);
  });

  it("never goes below 0", () => {
    expect(prozent(z({ anteil: -1 }))).toBe(0);
  });

  it("is 0 for an unlimited counter", () => {
    expect(prozent(z({ limit: null, anteil: null }))).toBe(0);
  });
});

describe("ton", () => {
  it("is danger once the limit is reached, even without the warning flag", () => {
    expect(ton(z({ erreicht: true, warnung: false }))).toBe("danger");
  });

  it("is warning before the wall", () => {
    expect(ton(z({ warnung: true }))).toBe("warning");
  });

  it("is neutral for unlimited, never green", () => {
    expect(ton(z({ limit: null, anteil: null }))).toBe("neutral");
  });

  it("is success otherwise", () => {
    expect(ton(z())).toBe("success");
  });
});

describe("verbrauchText", () => {
  it("names both numbers", () => {
    expect(verbrauchText(z({ benutzt: 37, limit: 100 }))).toBe("37 von 100");
  });

  it("appends MB for storage", () => {
    expect(verbrauchText(z({ key: "speicher_mb", benutzt: 3, limit: 1024 }))).toBe("3 MB von 1024 MB");
  });

  it("says unlimited instead of showing a null", () => {
    expect(verbrauchText(z({ benutzt: 900, limit: null }))).toBe("900 — unbegrenzt");
  });
});

describe("periodeText", () => {
  it("distinguishes a monthly counter from a stock", () => {
    expect(periodeText(z({ periode: "monat" }))).toBe("in diesem Monat");
    expect(periodeText(z({ periode: "bestand" }))).toBe("insgesamt");
  });
});

describe("warnungen", () => {
  it("puts a reached limit before a merely warning one", () => {
    const list = warnungen([
      z({ key: "a", warnung: true }),
      z({ key: "b", erreicht: true }),
    ]);
    expect(list.map((x) => x.key)).toEqual(["b", "a"]);
  });

  it("ignores healthy counters and unlimited ones", () => {
    expect(warnungen([z(), z({ limit: null, anteil: null, erreicht: true })])).toEqual([]);
  });
});

describe("naechsterReset", () => {
  it("is the first of the following month", () => {
    expect(naechsterReset("2026-09-01T00:00:00+00:00")).toContain("Oktober");
  });

  it("rolls over the year", () => {
    expect(naechsterReset("2026-12-01T00:00:00+00:00")).toContain("2027");
  });

  it("does not crash on nonsense", () => {
    expect(naechsterReset("not-a-date")).toBe("—");
  });
});
