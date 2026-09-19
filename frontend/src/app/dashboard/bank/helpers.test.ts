import type { TxRow } from "./types";
import { describe, expect, it } from "vitest";

import { SICHER_AB, confidenceTone, correctionsFor, istSicher, ohneVorschlag, toRow } from "./helpers";

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

describe("toRow — Betrag-Gedächtnis", () => {
  it("carries the description suggestion and leaves it undefined when the backend sends none", () => {
    const withHint = toRow({ beschreibung: "E-BANKING-AUFTRAG", kt_soll: "6260", betrag: 770.6, beschreibung_vorschlag: "Cembra Money, Leasing" }, 0);
    expect(withHint.vorschlag).toBe("Cembra Money, Leasing");
    expect(withHint.Beschreibung).toBe("E-BANKING-AUFTRAG");
    expect(toRow({ beschreibung: "Coop", kt_soll: "6500", betrag: 10, beschreibung_vorschlag: "" }, 0).vorschlag).toBeUndefined();
  });
});

// --- B-91: one threshold, and the bulk button obeys it --------------------

describe("istSicher", () => {
  const zeile = (confidence: number | undefined, suggSoll: string | undefined = "6260") =>
    ({ confidence, suggSoll }) as Pick<TxRow, "confidence" | "suggSoll">;

  it("92 % with a proposal is sicher", () => expect(istSicher(zeile(0.92))).toBe(true));
  it("the threshold itself is sicher", () => expect(istSicher(zeile(SICHER_AB))).toBe(true));
  it("35 % is not — the Sammelaufträge from the first run", () => expect(istSicher(zeile(0.35))).toBe(false));
  it("72 % is not either, though it looks confident", () => expect(istSicher(zeile(0.72))).toBe(false));
  // Not `zeile(0.99, undefined)`: a default parameter fires on an explicit
  // `undefined`, so that call silently kept the "6260" and asserted the opposite
  // of what it reads like. Written 2026-09-18, first actually run 2026-09-19.
  it("no proposal is never sicher, whatever the number says", () =>
    expect(istSicher({ confidence: 0.99, suggSoll: undefined })).toBe(false));
  it("and neither is an empty one — B-92 sends those now", () =>
    expect(istSicher({ confidence: 0.99, suggSoll: "" })).toBe(false));
  it("missing confidence reads as zero, not as certain", () => expect(istSicher(zeile(undefined))).toBe(false));
  it("the badge and the button agree on the same line", () => {
    expect(confidenceTone(SICHER_AB).tone).toBe("success");
    expect(confidenceTone(SICHER_AB - 0.01).tone).not.toBe("success");
  });
});

// --- B-92: a proposal the classifier does not believe is blank, not wrong -----

describe("ohneVorschlag", () => {
  it("an empty account is not a proposal — it is a row the Abgleich will resolve", () => {
    expect(ohneVorschlag({ suggSoll: "" })).toBe(true);
    expect(ohneVorschlag({ suggSoll: undefined })).toBe(true);
    expect(ohneVorschlag({ suggSoll: "6260" })).toBe(false);
  });

  it("the blank rows are never counted as sicher", () => {
    const leer = { confidence: 0, suggSoll: "" } as Pick<TxRow, "confidence" | "suggSoll">;
    expect(istSicher(leer)).toBe(false);
    expect(ohneVorschlag(leer)).toBe(true);
  });

  it("toRow carries the reason the backend gave, and nothing when there is none", () => {
    const leer = toRow(
      { beschreibung: "E-BANKING-SAMMELAUFTRAG", kt_soll: "", betrag: 770.6, confidence: 0, source: "Kein Vorschlag", begruendung: "Kein Gegenpart im Text — wird im Abgleich aufgelöst." },
      0
    );
    expect(leer.KtSoll).toBe("");
    expect(leer.begruendung).toContain("Abgleich");
    expect(ohneVorschlag(leer)).toBe(true);
    expect(toRow({ beschreibung: "Swisscom", kt_soll: "6500", betrag: 59 }, 0).begruendung).toBeUndefined();
  });
});
