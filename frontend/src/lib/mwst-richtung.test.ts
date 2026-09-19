import { describe, expect, it } from "vitest";

import { mwstRichtung, mwstRichtungLabel, mwstSatzLabel } from "./mwst-richtung";

// B-93: the sign is a direction, not a negative rate.

describe("mwstRichtung", () => {
  it("a negative rate is Umsatzsteuer — what we owe on our own revenue", () => {
    expect(mwstRichtung("-8.10")).toBe("umsatz");
    expect(mwstRichtung(-2.6)).toBe("umsatz");
  });

  it("a positive rate is Vorsteuer — what we paid and reclaim", () => {
    expect(mwstRichtung("8.10")).toBe("vorsteuer");
    expect(mwstRichtung(3.8)).toBe("vorsteuer");
  });

  it("nothing, zero and nonsense are no direction at all", () => {
    for (const v of ["", null, undefined, "0", 0, "abc"]) {
      expect(mwstRichtung(v as string)).toBe("keine");
      expect(mwstSatzLabel(v as string)).toBe("");
      expect(mwstRichtungLabel(v as string)).toBe("");
    }
  });
});

describe("mwstSatzLabel", () => {
  it("drops the sign — the user never needed to see it", () => {
    expect(mwstSatzLabel("-8.10")).toBe("8.10 %");
    expect(mwstSatzLabel("8.1")).toBe("8.10 %");
    expect(mwstSatzLabel("2,6")).toBe("2.60 %");
  });

  it("labels the direction instead", () => {
    expect(mwstRichtungLabel("-8.10")).toBe("geschuldet");
    expect(mwstRichtungLabel("8.10")).toBe("Vorsteuer");
  });
});
