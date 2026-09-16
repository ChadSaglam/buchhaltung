import { describe, expect, it } from "vitest";
import { inboxKopf, inboxRows, istAnker, type HeuteSources } from "./heute";

const side = (over = {}) => ({ count: 0, total: 0, overdue_count: 0, overdue_total: 0, items: [], buckets: {}, ...over });

const quellen = (over: Partial<HeuteSources> = {}): HeuteSources => over as HeuteSources;

describe("was eine Zeile verdient", () => {
  it("shows nothing when nothing is waiting", () => {
    expect(inboxRows(quellen())).toEqual([]);
    expect(inboxKopf([], false)).toBe("Alles erledigt 🎉");
  });

  it("does not invent a row from a zero", () => {
    const rows = inboxRows(
      quellen({
        posten: { debitoren: side(), kreditoren: side() } as never,
        review: { count: 0, items: [], threshold: 0.8 } as never,
        email: { abgelehnt: 0, belege_24h: 0 } as never,
      }),
    );
    expect(rows).toEqual([]);
  });

  it("names overdue invoices with their amount", () => {
    const rows = inboxRows(
      quellen({ posten: { debitoren: side({ overdue_count: 3, overdue_total: 12400 }), kreditoren: side() } as never }),
    );
    expect(rows[0].titel).toBe("3 Rechnungen überfällig");
    expect(rows[0].satz).toContain("CHF 12'400.00");
    expect(rows[0].tone).toBe("danger");
  });

  it("uses the singular for one", () => {
    const rows = inboxRows(
      quellen({ posten: { debitoren: side({ overdue_count: 1, overdue_total: 900 }), kreditoren: side() } as never }),
    );
    expect(rows[0].titel).toBe("1 Rechnung überfällig");
  });

  it("names the one standing order that is missing", () => {
    const rows = inboxRows(
      quellen({ dauer: { fehlen: [{ label: "Miete", betrag: 1800 }] } as never }),
    );
    expect(rows[0].titel).toBe("Miete ist diesen Monat nicht rausgegangen");
    expect(rows[0].satz).toContain("CHF 1'800.00");
  });

  it("adds them up when several are missing", () => {
    const rows = inboxRows(
      quellen({ dauer: { fehlen: [{ label: "Miete", betrag: 1800 }, { label: "Leasing", betrag: 770.6 }] } as never }),
    );
    expect(rows[0].titel).toBe("2 monatliche Zahlungen fehlen");
    expect(rows[0].satz).toContain("CHF 2'570.60");
  });

  it("treats an account going below zero as the worst kind of news", () => {
    const rows = inboxRows(
      quellen({ liquiditaet: { tiefster_stand: -3200, tiefster_am: "2026-11-14" } as never }),
    );
    expect(rows[0].tone).toBe("danger");
    expect(rows[0].satz).toBe("Am 14.11. fehlen CHF 3'200.00.");
  });

  it("does not warn about a healthy account", () => {
    expect(inboxRows(quellen({ liquiditaet: { tiefster_stand: 4000, tiefster_am: "2026-11-14" } as never }))).toEqual([]);
  });

  it("asks for the tax reserve only when there is one to put aside", () => {
    const mit = inboxRows(quellen({ liquiditaet: { tiefster_stand: 9, steuer: { pro_quartal: 8200 } } as never }));
    expect(mit[0].titel).toBe("Steuern zurücklegen");
    const ohne = inboxRows(quellen({ liquiditaet: { tiefster_stand: 9, steuer: { pro_quartal: null } } as never }));
    expect(ohne).toEqual([]);
  });
});

describe("Reihenfolge", () => {
  it("puts what hurts first", () => {
    const rows = inboxRows(
      quellen({
        posten: { debitoren: side({ overdue_count: 2, overdue_total: 500 }), kreditoren: side() } as never,
        review: { count: 4 } as never,
        email: { abgelehnt: 0, belege_24h: 3 } as never,
        abgleich: { summary: { offene_zeilen: 5, vorschlaege: 2 } } as never,
      }),
    );
    expect(rows.map((r) => r.tone)).toEqual(["danger", "warning", "warning", "info", "info"]);
  });

  it("keeps the same order when only a number changes", () => {
    const bauen = (anzahl: number) =>
      inboxRows(
        quellen({
          review: { count: anzahl } as never,
          abgleich: { summary: { offene_zeilen: 5, vorschlaege: 0 } } as never,
        }),
      ).map((r) => r.id);
    expect(bauen(4)).toEqual(bauen(40));
  });

  it("gives every row a stable id", () => {
    const rows = inboxRows(
      quellen({ review: { count: 4 } as never, email: { abgelehnt: 1, belege_24h: 2 } as never }),
    );
    expect(new Set(rows.map((r) => r.id)).size).toBe(rows.length);
  });
});

describe("Kopfzeile und Ziel", () => {
  it("counts what is waiting", () => {
    expect(inboxKopf([{ id: "a" }] as never, false)).toBe("Eine Sache wartet auf Sie");
    expect(inboxKopf([{ id: "a" }, { id: "b" }] as never, false)).toBe("2 Sachen warten auf Sie");
  });

  it("says nothing final while it is still loading", () => {
    expect(inboxKopf([], true)).toBe("Wird geladen …");
  });

  it("knows a row that scrolls from a row that navigates", () => {
    const rows = inboxRows(
      quellen({
        review: { count: 1 } as never,
        liquiditaet: { tiefster_stand: 1, steuer: { pro_quartal: 100 } } as never,
      }),
    );
    expect(istAnker(rows.find((r) => r.id === "steuer-zuruecklegen")!)).toBe(true);
    expect(istAnker(rows.find((r) => r.id === "review-offen")!)).toBe(false);
  });
});
