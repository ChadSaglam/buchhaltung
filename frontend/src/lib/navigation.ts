import {
  BookOpen, Brain, Building2, CheckCheck, FilePlus2, FileText, GraduationCap, Inbox,
  Landmark, ListChecks, Mail, PackageCheck, Receipt, ScanLine, ScrollText, Settings,
  Sparkles, Sun, Wallet,
  type LucideIcon,
} from "lucide-react";

/**
 * The four surfaces of `docs/IA-2026-09-14.md`, plus "Mehr".
 *
 *     Sammeln  ──▶  Abgleichen  ──▶  Abschliessen
 *     (Belege)      (Bank)           (Monat · Quartal · Jahr)
 *
 * and **Heute**, where the system says what it needs from the user.
 *
 * This is step 5 of that document's migration path: the sidebar collapses to
 * four entries and a "Mehr" group, and every page that used to be its own menu
 * entry becomes a tab inside the surface it belongs to. The pages themselves
 * have not moved — every old URL still works and is now reachable as a tab, so
 * nothing bookmarked breaks and the file move stays a separate, boring refactor.
 *
 * "Einstellungen" is in the account dropdown (UserMenu) as well; it is listed
 * under Mehr so the command palette and the breadcrumbs can resolve it.
 */

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  section?: string;
}

export interface Surface extends NavItem {
  /** The question this surface answers — shown as its subtitle. */
  frage: string;
  /** Pages that live inside it, in tab order. The first one is the surface itself. */
  tabs: NavItem[];
  /**
   * Claim only this exact path, never what sits under it. Heute lives at
   * `/dashboard`, which is the prefix of every other page — without this it
   * would claim the whole app.
   */
  exact?: boolean;
}

export const SURFACES: Surface[] = [
  {
    label: "Heute",
    href: "/dashboard",
    icon: Sun,
    frage: "Was muss ich tun?",
    tabs: [],
    exact: true,
  },
  {
    label: "Belege",
    href: "/dashboard/rechnungen",
    icon: Inbox,
    frage: "Was ist reingekommen?",
    tabs: [
      { label: "Rechnungen", href: "/dashboard/rechnungen", icon: Receipt },
      { label: "Scanner", href: "/dashboard/scanner", icon: ScanLine },
      { label: "E-Mail-Eingang", href: "/dashboard/rechnungen/email", icon: Mail },
      { label: "Rechnung schreiben", href: "/dashboard/rechnungen/neu", icon: FilePlus2 },
    ],
  },
  {
    label: "Bank",
    href: "/dashboard/kontoauszug",
    icon: Landmark,
    frage: "Was ist passiert?",
    tabs: [
      { label: "Kontoauszug", href: "/dashboard/kontoauszug", icon: FileText },
      { label: "Abgleich", href: "/dashboard/abgleich", icon: CheckCheck },
      { label: "Buchungen", href: "/dashboard/insights", icon: Sparkles },
    ],
  },
  {
    label: "Abschluss",
    href: "/dashboard/abschluss",
    icon: PackageCheck,
    frage: "Ist alles sauber?",
    tabs: [],
  },
];

/** Power users and the Treuhänder — one group at the bottom, never in the way. */
export const MEHR: NavItem[] = [
  { label: "Überprüfung", href: "/dashboard/review", icon: ListChecks, section: "Mehr" },
  { label: "Lohn", href: "/dashboard/lohn", icon: Wallet, section: "Mehr" },
  { label: "Kontenplan", href: "/dashboard/kontenplan", icon: BookOpen, section: "Mehr" },
  { label: "Modell", href: "/dashboard/modell", icon: Brain, section: "Mehr" },
  { label: "Lernverlauf", href: "/dashboard/lernverlauf", icon: GraduationCap, section: "Mehr" },
  { label: "Audit-Protokoll", href: "/dashboard/audit", icon: ScrollText, section: "Mehr" },
  { label: "Einstellungen", href: "/dashboard/settings", icon: Settings, section: "Mehr" },
];

/** Reachable but never its own sidebar entry. */
const VERSTECKT: NavItem[] = [
  { label: "Firmenprofil", href: "/dashboard/rechnungen/firma", icon: Building2, section: "Belege" },
];

export const NAV_ITEMS: NavItem[] = SURFACES.map(({ label, href, icon }) => ({
  label,
  href,
  icon,
  section: "Surfaces",
}));

function byHref(items: NavItem[]): NavItem[] {
  // A surface's own route is also its first tab; the surface name wins, because
  // that is what the IA calls the page ("Belege", not "Rechnungen").
  const seen = new Set<string>();
  return items.filter((item) => (seen.has(item.href) ? false : seen.add(item.href)));
}

/** All navigable pages, one entry per route — palette, breadcrumbs, topbar. */
export const ALL_NAV_ITEMS: NavItem[] = byHref([
  ...SURFACES.map(({ label, href, icon, frage }) => ({ label, href, icon, section: frage })),
  ...SURFACES.flatMap((s) => s.tabs.map((t) => ({ ...t, section: s.label }))),
  ...MEHR,
  ...VERSTECKT,
]);

function matches(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

/** How specifically a surface claims `pathname`; 0 = not at all. */
function claim(surface: Surface, pathname: string): number {
  const own = surface.exact ? pathname === surface.href : matches(surface.href, pathname);
  const hrefs = [...(own ? [surface.href] : []), ...surface.tabs.map((t) => t.href).filter((h) => matches(h, pathname))];
  return hrefs.reduce((longest, href) => Math.max(longest, href.length), 0);
}

/**
 * The surface a path belongs to — its own href or any of its tabs.
 * The most specific claim wins, so "/dashboard" (Heute) does not swallow
 * "/dashboard/kontoauszug" (Bank).
 */
export function surfaceFor(pathname: string): Surface | undefined {
  let best: Surface | undefined;
  let bestClaim = 0;
  for (const surface of SURFACES) {
    const score = claim(surface, pathname);
    if (score > bestClaim) {
      best = surface;
      bestClaim = score;
    }
  }
  return best;
}

/**
 * The tabs to show on `pathname`, and which one is active.
 * Empty when the surface has none (Heute, Abschluss have their own in-page tabs).
 */
export function tabsFor(pathname: string): { tabs: NavItem[]; active: NavItem | undefined; surface: Surface | undefined } {
  const surface = surfaceFor(pathname);
  if (!surface || surface.tabs.length === 0) return { tabs: [], active: undefined, surface };
  const active = [...surface.tabs]
    .sort((a, b) => b.href.length - a.href.length)
    .find((t) => matches(t.href, pathname));
  return { tabs: surface.tabs, active, surface };
}

export function getNavSections() {
  const sections = new Map<string, NavItem[]>();
  sections.set("Surfaces", NAV_ITEMS);
  sections.set("Mehr", MEHR);
  return sections;
}

/** Resolve the active nav item for a pathname (longest matching href wins). */
export function getActiveNavItem(pathname: string): NavItem | undefined {
  return [...ALL_NAV_ITEMS]
    .sort((a, b) => b.href.length - a.href.length)
    .find((item) => matches(item.href, pathname));
}
