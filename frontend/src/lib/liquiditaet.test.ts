import { describe, expect, it } from "vitest";
import {
  kurzdatum,
  liquiditaetSatz,
  liquiditaetTone,
  naechste,
  steuerSatz,
  type LiquiditaetResponse,
  type Steuer,
} from "./liquiditaet";
import { steuersatzWert } from "@/app/dashboard/rechnungen/firma/hooks/useFirma";

function report(overrides: Partial<LiquiditaetResponse> = {}): LiquiditaetResponse {
  return {
    stichtag: "2026-06-15",
    bis: "2026-09-13",
    stand_heute: 20000,
    eingang: 5000,
    ausgang: 3000,
    prognose: 22000,
    tiefster_stand: 20000,
    tiefster_am: "2026-06-15",
    positionen: [],
    dauerbuchungen: [],
    monate: [],
    warnungen: [],
    steuer: null,
    ...overrides,
  } as LiquiditaetResponse;
}

describe("liquiditaetTone", () => {
  it("is red when the balance dips below zero at any point", () => {
    // It ends comfortably, but there is a day in between with no money.
    expect(liquiditaetTone(report({ tiefster_stand: -500, prognose: 40000 }))).toBe("danger");
  });

  it("is amber when less than a month of outgoings is left", () => {
    expect(liquiditaetTone(report({ ausgang: 30000, tiefster_stand: 4000 }))).toBe("warning");
  });

  it("is green with a month of cover", () => {
    expect(liquiditaetTone(report({ ausgang: 30000, tiefster_stand: 15000 }))).toBe("success");
  });

  it("does not crash before the first response", () => {
    expect(liquiditaetTone(undefined)).toBe("success");
  });
});

describe("liquiditaetSatz", () => {
  it("names the day and the gap when the money runs out", () => {
    const text = liquiditaetSatz(report({ tiefster_stand: -1234.5, tiefster_am: "2026-07-20" }));
    expect(text).toContain("20.07.");
    expect(text).toContain("CHF 1'234.50");
  });

  it("names the lowest point when it stays positive", () => {
    expect(liquiditaetSatz(report({ tiefster_stand: 8000, tiefster_am: "2026-08-01" }))).toContain("CHF 8'000.00");
  });
});

describe("steuerSatz", () => {
  const steuer = (o: Partial<Steuer> = {}): Steuer =>
    ({ jahr: 2026, ertrag: 0, aufwand: 0, gewinn: 0, schon_zurueckgestellt: 0, quelle: "", hinweis: "", ...o }) as Steuer;

  it("says what to set aside this quarter", () => {
    expect(steuerSatz(steuer({ satz: 14.43, pro_quartal: 2886 }))).toBe("Dieses Quartal CHF 2'886.00 zurücklegen");
  });

  it("does not invent a number without a rate", () => {
    expect(steuerSatz(steuer({ satz: null, pro_quartal: null }))).toBe("Kein Steuersatz hinterlegt");
  });

  it("says nothing is owed on a loss", () => {
    expect(steuerSatz(steuer({ satz: 14.43, pro_quartal: 0 }))).toBe("Nichts zurückzulegen");
  });
});

describe("kurzdatum", () => {
  it("shortens an ISO date to day and month", () => {
    expect(kurzdatum("2026-09-13")).toBe("13.09.");
    expect(kurzdatum(null)).toBe("–");
  });
});

describe("naechste", () => {
  it("takes the first few movements, in the order the API sent them", () => {
    const positionen = Array.from({ length: 9 }, (_, i) => ({
      datum: `2026-07-0${i + 1}`,
      label: `P${i}`,
      betrag: 100,
      quelle: "debitor",
      document_id: null,
      ueberfaellig: false,
    }));
    expect(naechste(report({ positionen } as Partial<LiquiditaetResponse>))).toHaveLength(5);
    expect(naechste(undefined)).toEqual([]);
  });
});

describe("steuersatzWert", () => {
  it("reads what people type", () => {
    expect(steuersatzWert("14.43")).toBe(14.43);
    expect(steuersatzWert("14,43")).toBe(14.43);
    expect(steuersatzWert(" 12 ")).toBe(12);
  });

  it("returns null for anything that is not a Swiss rate", () => {
    expect(steuersatzWert("")).toBeNull();      // clearing it is allowed
    expect(steuersatzWert("abc")).toBeNull();
    expect(steuersatzWert("-3")).toBeNull();
    expect(steuersatzWert("144")).toBeNull();   // a percentage sign too far
  });
});
