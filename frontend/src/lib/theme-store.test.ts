import { describe, expect, it } from "vitest";
import { ACCENTS, type Accent } from "./theme-store";

/**
 * B-58: white sits on `--primary` (see `--cd-color-brand-fg`) and `brand-600`
 * is the text colour on light cards, so both have to clear WCAG AA's 4.5:1.
 * Emerald was 3.77:1 and amber 3.19:1 before this.
 */

const WHITE = "#ffffff";
/** The darkest surface a `brand-300` label sits on. */
const DARK_SURFACE = "#0b1220";

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const channels = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const linear = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const accents = Object.keys(ACCENTS) as Accent[];

describe("accent contrast", () => {
  it.each(accents)("%s: white on the primary button clears 4.5:1", (accent) => {
    expect(contrast(ACCENTS[accent].primary, WHITE)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(accents)("%s: brand-600 text clears 4.5:1 on a light card", (accent) => {
    expect(contrast(ACCENTS[accent].b600, WHITE)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(accents)("%s: brand-300 text clears 4.5:1 on a dark surface", (accent) => {
    expect(contrast(ACCENTS[accent].b300, DARK_SURFACE)).toBeGreaterThanOrEqual(4.5);
  });

  it("knows a failing pair when it sees one", () => {
    expect(contrast("#d97706", WHITE)).toBeLessThan(4.5); // the old amber
  });
});
