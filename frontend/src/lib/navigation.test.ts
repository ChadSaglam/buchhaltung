import { describe, expect, it } from "vitest";
import {
  ALL_NAV_ITEMS,
  MEHR,
  NAV_ITEMS,
  SURFACES,
  getActiveNavItem,
  getNavSections,
  surfaceFor,
  tabsFor,
} from "./navigation";

/**
 * The IA contract (`docs/IA-2026-09-14.md`): four surfaces and a "Mehr" group,
 * and every page that used to be its own menu entry still reachable.
 */

describe("the sidebar", () => {
  it("has exactly the four surfaces", () => {
    expect(NAV_ITEMS.map((i) => i.label)).toEqual(["Heute", "Belege", "Bank", "Abschluss"]);
  });

  it("puts everything else under Mehr", () => {
    expect(getNavSections().get("Mehr")).toBe(MEHR);
    expect(MEHR.map((i) => i.label)).toContain("Kontenplan");
    expect(MEHR.map((i) => i.label)).toContain("Einstellungen");
  });

  it("does not list a page twice", () => {
    const hrefs = ALL_NAV_ITEMS.map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});

describe("surfaceFor", () => {
  it.each([
    ["/dashboard", "Heute"],
    ["/dashboard/rechnungen", "Belege"],
    ["/dashboard/scanner", "Belege"],
    ["/dashboard/rechnungen/neu", "Belege"],
    ["/dashboard/rechnungen/email", "Belege"],
    ["/dashboard/kontoauszug", "Bank"],
    ["/dashboard/abgleich", "Bank"],
    ["/dashboard/insights", "Bank"],
    ["/dashboard/abschluss", "Abschluss"],
  ])("%s belongs to %s", (path, label) => {
    expect(surfaceFor(path)?.label).toBe(label);
  });

  it("does not let Heute swallow every page below it", () => {
    expect(surfaceFor("/dashboard/kontoauszug")?.label).not.toBe("Heute");
  });

  it("returns nothing for a page under Mehr", () => {
    expect(surfaceFor("/dashboard/modell")).toBeUndefined();
    expect(surfaceFor("/dashboard/settings")).toBeUndefined();
  });
});

describe("tabsFor", () => {
  it("marks the tab the user is on", () => {
    const { tabs, active } = tabsFor("/dashboard/scanner");
    expect(tabs.map((t) => t.label)).toEqual(["Rechnungen", "Scanner", "E-Mail-Eingang", "Rechnung schreiben"]);
    expect(active?.label).toBe("Scanner");
  });

  it("prefers the longer route when two tabs share a prefix", () => {
    expect(tabsFor("/dashboard/rechnungen/neu").active?.label).toBe("Rechnung schreiben");
    expect(tabsFor("/dashboard/rechnungen").active?.label).toBe("Rechnungen");
  });

  it("shows no tab row where the page brings its own", () => {
    expect(tabsFor("/dashboard").tabs).toEqual([]);
    expect(tabsFor("/dashboard/abschluss").tabs).toEqual([]);
  });

  it("shows no tab row under Mehr", () => {
    expect(tabsFor("/dashboard/audit").tabs).toEqual([]);
  });
});

describe("getActiveNavItem", () => {
  it("still resolves every old route, so no bookmark broke", () => {
    for (const href of [
      "/dashboard",
      "/dashboard/insights",
      "/dashboard/rechnungen",
      "/dashboard/rechnungen/neu",
      "/dashboard/rechnungen/firma",
      "/dashboard/rechnungen/email",
      "/dashboard/kontoauszug",
      "/dashboard/abgleich",
      "/dashboard/scanner",
      "/dashboard/abschluss",
      "/dashboard/kontenplan",
      "/dashboard/modell",
      "/dashboard/lernverlauf",
      "/dashboard/review",
      "/dashboard/audit",
      "/dashboard/settings",
    ]) {
      expect(getActiveNavItem(href)?.href, href).toBe(href);
    }
  });

  it("falls back to the nearest parent for a page with no entry of its own", () => {
    expect(getActiveNavItem("/dashboard/rechnungen/123")?.href).toBe("/dashboard/rechnungen");
  });
});

describe("the surfaces themselves", () => {
  it("each answer one question, in the user's words", () => {
    expect(SURFACES.map((s) => s.frage)).toEqual([
      "Was muss ich tun?",
      "Was ist reingekommen?",
      "Was ist passiert?",
      "Ist alles sauber?",
    ]);
  });

  it("start their tab list with the surface's own route", () => {
    for (const surface of SURFACES) {
      if (surface.tabs.length === 0) continue;
      expect(surface.tabs[0].href, surface.label).toBe(surface.href);
    }
  });
});
