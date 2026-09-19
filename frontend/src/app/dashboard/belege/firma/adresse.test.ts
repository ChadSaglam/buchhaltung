import { describe, expect, it } from "vitest";

import { adressWarnung, strasseEnthaeltNummer } from "./adresse";

// B-103: the real Rechnung 2026-0001 is the first case.

describe("strasseEnthaeltNummer", () => {
  it("finds a house number at the end", () => {
    expect(strasseEnthaeltNummer("Bungertenstrasse 57")).toBe(true);
    expect(strasseEnthaeltNummer("Rue du Pont 12b")).toBe(true);
    expect(strasseEnthaeltNummer("  Hohlstrasse 485A  ")).toBe(true);
  });

  it("leaves a plain street alone", () => {
    expect(strasseEnthaeltNummer("Bungertenstrasse")).toBe(false);
    expect(strasseEnthaeltNummer("")).toBe(false);
  });

  it("does not mistake a number inside the name for a house number", () => {
    expect(strasseEnthaeltNummer("Route 66 Strasse")).toBe(false);
  });
});

describe("adressWarnung", () => {
  it("warns on exactly the combination that produced the wrong Zahlteil", () => {
    const satz = adressWarnung("Bungertenstrasse 57", "485A");
    expect(satz).toContain("57");
    expect(satz).toContain("485A");
    expect(satz).toContain("Bungertenstrasse 57 485A");
  });

  it("says nothing when the street carries the number and Nr. is empty", () => {
    // A one-field address reaches StrtNmOrAdrLine1 unchanged and reads correctly.
    expect(adressWarnung("Bungertenstrasse 57", "")).toBe("");
  });

  it("says nothing when the fields are filled the way they are meant to be", () => {
    expect(adressWarnung("Bungertenstrasse", "57")).toBe("");
  });

  it("says nothing on an empty form", () => {
    expect(adressWarnung("", "")).toBe("");
  });
});
