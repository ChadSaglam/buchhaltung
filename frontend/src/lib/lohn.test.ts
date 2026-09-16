import { describe, expect, it } from "vitest";
import {
  aktive,
  anteilSatz,
  anzeigeName,
  bereitschaftSatz,
  bereitschaftTone,
  betragWert,
  istAbgerechnet,
  monatsende,
  monatsname,
  nettoSatz,
  periodeLabel,
  satzLabel,
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
