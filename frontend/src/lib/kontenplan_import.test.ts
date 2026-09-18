import { describe, expect, it } from "vitest";
import type { KontenplanImportVorschau, KontenplanImportZeile } from "@/lib/api-schema";
import {
  danach,
  doppelteSatz,
  doppelteZeilen,
  folgenSatz,
  istWirkungslos,
  sortiert,
  uebernehmbar,
  verliertDaten,
} from "@/lib/kontenplan_import";

function v(over: Partial<KontenplanImportVorschau> = {}): KontenplanImportVorschau {
  return {
    zeilen: [],
    entfaellt: [],
    spalte_konto: "Konto",
    spalte_bezeichnung: "Beschreibung",
    zaehler: { neu: 0, geaendert: 0, unveraendert: 0, ungueltig: 0 },
    ...over,
  } as KontenplanImportVorschau;
}

function zaehler(neu = 0, geaendert = 0, unveraendert = 0, ungueltig = 0) {
  return { neu, geaendert, unveraendert, ungueltig };
}

describe("uebernehmbar", () => {
  it("counts everything the import would write", () => {
    expect(uebernehmbar(v({ zaehler: zaehler(3, 2, 1) }))).toBe(6);
  });

  it("never counts a row that could not be read", () => {
    expect(uebernehmbar(v({ zaehler: zaehler(3, 0, 0, 9) }))).toBe(3);
  });
});

describe("danach", () => {
  it("adds only the new ones when supplementing", () => {
    expect(danach(v({ zaehler: zaehler(3, 2) }), "ergaenzen", 10)).toBe(13);
  });

  it("is the file itself when replacing", () => {
    expect(danach(v({ zaehler: zaehler(3, 2, 1) }), "ersetzen", 10)).toBe(6);
  });
});

describe("verliertDaten", () => {
  it("is false for ergaenzen, whatever the file leaves out", () => {
    expect(verliertDaten(v({ entfaellt: ["6500", "6510"] }), "ergaenzen")).toBe(false);
  });

  it("is true for ersetzen when something would disappear", () => {
    expect(verliertDaten(v({ entfaellt: ["6500"] }), "ersetzen")).toBe(true);
  });

  it("is false for ersetzen when the file covers everything", () => {
    expect(verliertDaten(v({ entfaellt: [] }), "ersetzen")).toBe(false);
  });
});

describe("folgenSatz", () => {
  it("leads with the deletion, because that is the part that hurts", () => {
    const satz = folgenSatz(v({ entfaellt: ["6500", "6510"], zaehler: zaehler(1, 1) }), "ersetzen");
    expect(satz.startsWith("2 Konten werden gelöscht")).toBe(true);
  });

  it("uses the singular for one account", () => {
    expect(folgenSatz(v({ entfaellt: ["6500"], zaehler: zaehler(1) }), "ersetzen")).toContain("1 Konto wird gelöscht");
  });

  it("says nothing is lost when supplementing", () => {
    expect(folgenSatz(v({ entfaellt: ["6500"], zaehler: zaehler(1) }), "ergaenzen")).toContain("bleibt");
  });

  it("says so when replacing loses nothing", () => {
    expect(folgenSatz(v({ zaehler: zaehler(1) }), "ersetzen")).toContain("nichts wird gelöscht");
  });
});

describe("istWirkungslos", () => {
  it("is true when the file changes nothing", () => {
    expect(istWirkungslos(v({ zaehler: zaehler(0, 0, 12) }), "ergaenzen")).toBe(true);
  });

  it("is false when a replace would still delete something", () => {
    expect(istWirkungslos(v({ entfaellt: ["6500"], zaehler: zaehler(0, 0, 12) }), "ersetzen")).toBe(false);
  });

  it("is false when there is a new account", () => {
    expect(istWirkungslos(v({ zaehler: zaehler(1) }), "ergaenzen")).toBe(false);
  });
});

describe("sortiert", () => {
  it("puts the rows the user has to fix first", () => {
    const zeilen = [
      { konto: "1020", bezeichnung: "Bank", status: "unveraendert", bisher: "Bank", grund: "", quelle: 1 },
      { konto: "6500", bezeichnung: "Büro", status: "neu", bisher: "", grund: "", quelle: 2 },
      { konto: "TOTAL", bezeichnung: "Summe", status: "ungueltig", bisher: "", grund: "x", quelle: 3 },
      { konto: "1000", bezeichnung: "Kasse", status: "geaendert", bisher: "Kassa", grund: "", quelle: 4 },
    ] as KontenplanImportZeile[];

    expect(sortiert(zeilen).map((z) => z.status)).toEqual(["ungueltig", "geaendert", "neu", "unveraendert"]);
  });

  it("orders by account number inside a group", () => {
    const zeilen = [
      { konto: "6500", bezeichnung: "b", status: "neu", bisher: "", grund: "", quelle: 1 },
      { konto: "1020", bezeichnung: "a", status: "neu", bisher: "", grund: "", quelle: 2 },
    ] as KontenplanImportZeile[];

    expect(sortiert(zeilen).map((z) => z.konto)).toEqual(["1020", "6500"]);
  });

  it("does not mutate its input", () => {
    const zeilen = [
      { konto: "6500", bezeichnung: "b", status: "neu", bisher: "", grund: "", quelle: 1 },
      { konto: "1020", bezeichnung: "a", status: "ungueltig", bisher: "", grund: "", quelle: 2 },
    ] as KontenplanImportZeile[];
    sortiert(zeilen);
    expect(zeilen[0].konto).toBe("6500");
  });
});

// --- B-85: dieselbe Bezeichnung, zwei Nummern --------------------------------

describe("doppelteSatz", () => {
  const zeile = (over: Partial<KontenplanImportZeile>): KontenplanImportZeile =>
    ({ konto: "2205", bezeichnung: "Geschuldete MWST", status: "neu", bisher: "", grund: "", quelle: 1, doppelt_zu: "", ...over }) as KontenplanImportZeile;

  const vorschau = (zeilen: KontenplanImportZeile[]): KontenplanImportVorschau =>
    ({
      zeilen,
      entfaellt: [],
      spalte_konto: "Konto",
      spalte_bezeichnung: "Beschreibung",
      doppelt: zeilen.filter((z) => z.doppelt_zu).length,
      zaehler: { neu: zeilen.length, geaendert: 0, unveraendert: 0, ungueltig: 0 },
    }) as KontenplanImportVorschau;

  it("names both numbers so the owner can choose", () => {
    const satz = doppelteSatz(vorschau([zeile({ doppelt_zu: "2200" })]), "ergaenzen");
    expect(satz).toContain("2205");
    expect(satz).toContain("2200");
  });

  it("says nothing when no row collides", () => {
    expect(doppelteSatz(vorschau([zeile({})]), "ergaenzen")).toBe("");
  });

  it("says nothing in Ersetzen — the old account is gone anyway", () => {
    expect(doppelteSatz(vorschau([zeile({ doppelt_zu: "2200" })]), "ersetzen")).toBe("");
  });

  it("counts instead of listing when there are several", () => {
    const v = vorschau([zeile({ doppelt_zu: "2200" }), zeile({ konto: "3201", doppelt_zu: "3200" })]);
    expect(doppelteSatz(v, "ergaenzen")).toContain("2 Konten");
    expect(doppelteZeilen(v)).toHaveLength(2);
  });
});
