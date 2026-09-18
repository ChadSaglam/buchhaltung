import { describe, expect, it } from "vitest";
import {
  AMTLICHE_QUELLEN,
  PFLICHTSAETZE,
  aktive,
  anteilSatz,
  anzeigeName,
  bereitschaftSatz,
  bereitschaftTone,
  betragWert,
  freigabeSatz,
  istAbgerechnet,
  monatsende,
  monatsname,
  nettoSatz,
  periodeLabel,
  satzLabel,
  satzPlausibilitaet,
  satzWert,
  type Lohnlauf,
  type LohnSettings,
  type Mitarbeiter,
} from "./lohn";

const settings = (fehlt: string[]): LohnSettings => ({ fehlt, bereit: fehlt.length === 0 }) as LohnSettings;
const person = (over: Partial<Mitarbeiter> = {}): Mitarbeiter =>
  ({ id: 1, vorname: "Anna", name: "Muster", anzeige_name: "Anna Muster", austritt: null, ...over }) as Mitarbeiter;

describe("bereitschaft", () => {
  it("says it is ready when nothing is missing", () => {
    expect(bereitschaftSatz(settings([]))).toContain("Bereit");
    expect(bereitschaftTone(settings([]))).toBe("success");
  });

  it("names the one missing rate in the singular", () => {
    expect(bereitschaftSatz(settings(["FAK-Satz"]))).toBe("Noch nicht bereit. Es fehlt: FAK-Satz.");
  });

  it("lists every missing rate at once", () => {
    // Fixing them one round-trip at a time is how people give up.
    expect(bereitschaftSatz(settings(["UVG NBU-Satz", "FAK-Satz"]))).toContain("UVG NBU-Satz, FAK-Satz");
    expect(bereitschaftTone(settings(["FAK-Satz"]))).toBe("warning");
  });
});

describe("Eingaben", () => {
  it("reads a Swiss decimal comma", () => {
    expect(satzWert("1,6")).toBe(1.6);
    expect(betragWert("1'234,50")).toBe(1234.5);
  });

  it("treats an empty field as 'no value', not as zero", () => {
    // Clearing a voluntary rate means "not insured"; zero would mean "insured at 0 %".
    expect(satzWert("")).toBeNull();
    expect(betragWert("  ")).toBeNull();
  });

  it("rejects a rate outside 0–100", () => {
    expect(satzWert("250")).toBeNull();
    expect(satzWert("-3")).toBeNull();
  });

  it("rejects a negative amount", () => {
    expect(betragWert("-10")).toBeNull();
  });
});

describe("Darstellung", () => {
  it("prints a rate with two decimals and nothing for a fixed amount", () => {
    expect(satzLabel(5.3)).toBe("5.30 %");
    expect(satzLabel(0)).toBe("");
    expect(satzLabel(null)).toBe("");
  });

  it("names the period in German", () => {
    expect(monatsname(3)).toBe("März");
    expect(periodeLabel(2026, 12)).toBe("Dezember 2026");
  });

  it("spells out the sum on the payslip", () => {
    const lauf = { brutto: 6000, abzuege_total: 780, netto: 5220, anteil: 1 } as Lohnlauf;
    expect(nettoSatz(lauf)).toBe("CHF 6'000.00 brutto − CHF 780.00 Abzüge = CHF 5'220.00 netto");
  });

  it("says out loud when a month is only partly worked", () => {
    expect(anteilSatz({ anteil: 0.5 } as Lohnlauf)).toContain("50 %");
    expect(anteilSatz({ anteil: 1 } as Lohnlauf)).toBe("");
  });

  it("knows an issued payslip from a preview", () => {
    expect(istAbgerechnet({ abrechnung_id: 7 } as Lohnlauf)).toBe(true);
    expect(istAbgerechnet({ abrechnung_id: null } as Lohnlauf)).toBe(false);
  });
});

describe("Mitarbeiterliste", () => {
  it("keeps someone who left after the period", () => {
    const liste = [person({ id: 1 }), person({ id: 2, austritt: "2026-03-31" })];
    expect(aktive(liste, monatsende(2026, 3)).map((m) => m.id)).toEqual([1, 2]);
  });

  it("drops someone who left before it", () => {
    const liste = [person({ id: 1 }), person({ id: 2, austritt: "2026-02-28" })];
    expect(aktive(liste, monatsende(2026, 3)).map((m) => m.id)).toEqual([1]);
  });

  it("knows the last day of February", () => {
    expect(monatsende(2026, 2)).toBe("2026-02-28");
    expect(monatsende(2028, 2)).toBe("2028-02-29");
  });

  it("falls back to an id when a name is missing", () => {
    expect(anzeigeName(person({ vorname: "", name: "", anzeige_name: "" }))).toBe("Mitarbeiter 1");
  });
});

describe("Freigabe", () => {
  it("spells out that the watermark is still on", () => {
    const s = { freigegeben: false, wasserzeichen: "Nicht für die Einreichung" } as LohnSettings;
    expect(freigabeSatz(s)).toContain("Nicht für die Einreichung");
  });

  it("says it is cleared once signed off", () => {
    const s = { freigegeben: true, wasserzeichen: "" } as LohnSettings;
    expect(freigabeSatz(s)).toContain("ohne Wasserzeichen");
  });
});

// --- B-98 Stufe 1: name the document, catch the decimal point ----------------

describe("PFLICHTSAETZE — jedes Feld nennt sein Dokument", () => {
  it("every compulsory rate says which letter it is printed on", () => {
    for (const satz of PFLICHTSAETZE) {
      expect(satz.dokument.length).toBeGreaterThan(20);
      expect(satz.plausibel[0]).toBeLessThan(satz.plausibel[1]);
    }
  });

  it("only official sources are linked", () => {
    for (const q of AMTLICHE_QUELLEN) expect(q.href).toMatch(/^https:\/\/www\.ahv-iv\.ch\//);
  });
});

describe("satzPlausibilitaet", () => {
  it("says nothing about a normal rate", () => {
    expect(satzPlausibilitaet("uvg_nbu_satz", "1.6")).toBe("");
    expect(satzPlausibilitaet("fak_satz", "1.2")).toBe("");
  });

  it("the 0.5 % NBU from the owner's own June payslip is fine", () => {
    expect(satzPlausibilitaet("uvg_nbu_satz", "0.5")).toBe("");
  });

  it("flags a misplaced decimal point without blocking it", () => {
    expect(satzPlausibilitaet("uvg_nbu_satz", "16")).toContain("Ungewöhnlich");
    expect(satzPlausibilitaet("fak_satz", "0.01")).toContain("Komma");
  });

  it("an empty or cleared field is not a warning", () => {
    expect(satzPlausibilitaet("uvg_bu_satz", "")).toBe("");
    expect(satzPlausibilitaet("uvg_bu_satz", "0")).toBe("");
  });

  it("voluntary rates have no band — absent is an answer there", () => {
    expect(satzPlausibilitaet("ktg_satz_an", "99")).toBe("");
  });
});
