import { describe, expect, it } from "vitest";
import { absenderBekannt, belegeTitel } from "./helpers";

describe("absenderBekannt", () => {
  const liste = ["rechnung@lieferant.ch", "@treuhand.ch"];

  it("matches an exact address, case-insensitively", () => {
    expect(absenderBekannt("rechnung@lieferant.ch", liste)).toBe(true);
    expect(absenderBekannt("Rechnung@Lieferant.CH", liste)).toBe(true);
    expect(absenderBekannt("andere@lieferant.ch", liste)).toBe(false);
  });

  it("matches a whole domain", () => {
    expect(absenderBekannt("egal@treuhand.ch", liste)).toBe(true);
    expect(absenderBekannt("egal@treuhand.de", liste)).toBe(false);
  });

  it("says no when there is nothing to match", () => {
    expect(absenderBekannt("", liste)).toBe(false);
    expect(absenderBekannt("a@b.ch", [])).toBe(false);
    expect(absenderBekannt("a@b.ch", ["  "])).toBe(false);
  });
});

describe("belegeTitel", () => {
  it("counts in German", () => {
    expect(belegeTitel(0)).toBe("Belege per E-Mail");
    expect(belegeTitel(1)).toBe("1 neuer Beleg per E-Mail");
    expect(belegeTitel(3)).toBe("3 neue Belege per E-Mail");
  });
});
