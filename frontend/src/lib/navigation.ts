import {
  LayoutDashboard, FileText, ScanLine, BookOpen,
  Brain, GraduationCap, Settings, ListChecks, ScrollText, Sparkles,
  type LucideIcon,
} from "lucide-react";

/**
 * NAV_ITEMS drives the persistent sidebar navigation.
 *
 * Note: "Einstellungen" is intentionally NOT listed here — it already lives in
 * the user account dropdown (UserMenu). It is still reachable via the ⌘K command
 * palette through EXTRA_NAV_ITEMS below so power users keep a fast path to it.
 */

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  section?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, section: "Übersicht" },
  { label: "Insights & Suche", href: "/dashboard/insights", icon: Sparkles, section: "Übersicht" },
  { label: "Kontoauszug", href: "/dashboard/kontoauszug", icon: FileText, section: "Buchhaltung" },
  { label: "Scanner", href: "/dashboard/scanner", icon: ScanLine, section: "Buchhaltung" },
  { label: "Kontenplan", href: "/dashboard/kontenplan", icon: BookOpen, section: "AI & Training" },
  { label: "Modell", href: "/dashboard/modell", icon: Brain, section: "AI & Training" },
  { label: "Lernverlauf", href: "/dashboard/lernverlauf", icon: GraduationCap, section: "AI & Training" },
  { label: "Überprüfung", href: "/dashboard/review", icon: ListChecks, section: "AI & Training" },
  { label: "Audit-Protokoll", href: "/dashboard/audit", icon: ScrollText, section: "System" },
];

/**
 * Pages that are not shown in the sidebar but should still be reachable from the
 * command palette (and used to resolve the active topbar title/breadcrumb).
 */
export const EXTRA_NAV_ITEMS: NavItem[] = [
  { label: "Einstellungen", href: "/dashboard/settings", icon: Settings, section: "System" },
];

/** All navigable pages (sidebar + extras) — used by palette, breadcrumbs, topbar. */
export const ALL_NAV_ITEMS: NavItem[] = [...NAV_ITEMS, ...EXTRA_NAV_ITEMS];

export function getNavSections() {
  const sections = new Map<string, NavItem[]>();
  for (const item of NAV_ITEMS) {
    const key = item.section ?? "Allgemein";
    if (!sections.has(key)) sections.set(key, []);
    sections.get(key)!.push(item);
  }
  return sections;
}

/** Resolve the active nav item for a pathname (longest matching href wins). */
export function getActiveNavItem(pathname: string): NavItem | undefined {
  return [...ALL_NAV_ITEMS]
    .sort((a, b) => b.href.length - a.href.length)
    .find((item) => pathname === item.href || pathname.startsWith(item.href + "/"));
}
