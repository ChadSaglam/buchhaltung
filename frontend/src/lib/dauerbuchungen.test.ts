import { describe, expect, it } from "vitest";
import {
  fehltSatz,
  kopfTone,
  kopfzeile,
  tagLabel,
  type Dauerbuchung,
  type DauerbuchungenResponse,
} from "./dauerbuchungen";

function entry(overrides: Partial<Dauerbuchung> = {}): Dauerbuchung {
  return {
    label: "Cembra Leasing",
    betrag: 770.6,
    monate: 3,
    letzter_monat: "2026-05",
    konto: "6200",
    tag: 5,
    status: "fehlt",
    faellig_am: "2026-06-05",
    tage_ueberfaellig: 15,
    schluessel: "cembra leasing",
    ...overrides,
  } as Dauerbuchung;
}

function response(overrides: Partial<DauerbuchungenResponse> = {}): DauerbuchungenResponse {
  return {
    stichtag: "2026-06-20",
    monat: "2026-06",
    eintraege: [entry()],
    fehlen: [entry()],
    offen_total: 770.6,
    monatstotal: 770.6,
    ...overrides,
  } as DauerbuchungenResponse;
}

describe("fehltSatz", () => {
  it("is the sentence this feature exists for", () => {
    expect(fehltSatz(entry())).toBe("Cembra Leasing CHF 770.60 fehlt diesen Monat (seit 15 Tagen).");
  });

  it("counts one day in the singular", () => {
    expect(fehltSatz(entry({ tage_ueberfaellig: 1 }))).toContain("seit einem Tag");
  });
});

describe("kopfzeile", () => {
  it("leads with what is missing", () => {
    expect(kopfzeile(response())).toBe("1 Zahlung fehlt: CHF 770.60");
  });

  it("adds several missing payments up", () => {
    const two = response({ fehlen: [entry(), entry({ label: "Miete", betrag: 1800 })] });
    expect(kopfzeile(two)).toBe("2 Zahlungen fehlen: CHF 2'570.60");
  });

  it("says what is still to come when nothing is late", () => {
    expect(kopfzeile(response({ fehlen: [], offen_total: 200 }))).toBe("CHF 200.00 gehen diesen Monat noch raus");
  });

  it("says so when the month is done", () => {
    expect(kopfzeile(response({ fehlen: [], offen_total: 0 }))).toBe("Alles bezahlt diesen Monat");
  });

  it("does not pretend to know a tenant with no history", () => {
    expect(kopfzeile(response({ eintraege: [], fehlen: [], offen_total: 0 }))).toBe(
      "Noch keine wiederkehrenden Zahlungen erkannt",
    );
  });

  it("survives the first render, before any data", () => {
    expect(kopfzeile(undefined)).toBe("");
    expect(kopfTone(undefined)).toBe("neutral");
  });
});

describe("kopfTone", () => {
  it("is amber only when something is actually late", () => {
    expect(kopfTone(response())).toBe("warning");
    expect(kopfTone(response({ fehlen: [], offen_total: 200 }))).toBe("neutral");
    expect(kopfTone(response({ fehlen: [], offen_total: 0 }))).toBe("success");
  });
});

describe("tagLabel", () => {
  it("reads like a German sentence", () => {
    expect(tagLabel(entry({ tag: 5 }))).toBe("am 5.");
  });
});
