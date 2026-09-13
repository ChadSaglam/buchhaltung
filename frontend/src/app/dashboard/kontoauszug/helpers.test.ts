import { describe, expect, it } from "vitest";

import { correctionsFor, toRow } from "./helpers";

const classified = (beschreibung: string, kt_soll: string, kt_haben = "1020") =>
  toRow({ beschreibung, kt_soll, kt_haben, betrag: 10, mwst_code: "I81", mwst_pct: "8.1" }, 0);

describe("correctionsFor (B-45)", () => {
  it("skips rows the user left as suggested — accepting a prediction is not a correction", () => {
    expect(correctionsFor([classified("Migros", "4000")])).toEqual([]);
  });

  it("sends the suggestion as original and the edit as corrected, with the VAT of the row", () => {
    const row = { ...classified("Migros", "4000"), KtSoll: "6000" };
    expect(correctionsFor([row])).toEqual([
      {
        beschreibung: "Migros",
        original_soll: "4000",
        original_haben: "1020",
        corrected_soll: "6000",
        corrected_haben: "1020",
        corrected_mwst_code: "I81",
        corrected_mwst_pct: "8.1",
      },
    ]);
  });

  it("treats a changed Haben account as a correction too, and ignores rows without Soll", () => {
    const haben = { ...classified("Swisscom", "6510"), KtHaben: "2000" };
    const empty = { ...classified("?", ""), KtSoll: "" };
    expect(correctionsFor([haben, empty]).map((c) => c.corrected_haben)).toEqual(["2000"]);
  });
});
