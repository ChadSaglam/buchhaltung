import {
  FileText, ScanLine, Play, Plus, Download, ListChecks, Sparkles,
  type LucideIcon,
} from "lucide-react";

/**
 * Per-page quick actions rendered next to the breadcrumbs in the Topbar.
 * Each action is a simple navigation link (kept dependency-free so it works
 * on every page without importing page-local state).
 */
export interface QuickAction {
  label: string;
  href: string;
  icon: LucideIcon;
}

const MAP: Record<string, QuickAction[]> = {
  "/dashboard": [
    { label: "Kontoauszug", href: "/dashboard/kontoauszug", icon: FileText },
    { label: "Scanner", href: "/dashboard/scanner", icon: ScanLine },
    { label: "Insights", href: "/dashboard/insights", icon: Sparkles },
  ],
  "/dashboard/kontoauszug": [
    { label: "Scanner öffnen", href: "/dashboard/scanner", icon: ScanLine },
  ],
  "/dashboard/scanner": [
    { label: "Kontoauszug", href: "/dashboard/kontoauszug", icon: FileText },
  ],
  "/dashboard/kontenplan": [
    { label: "Modell trainieren", href: "/dashboard/modell", icon: Play },
  ],
  "/dashboard/modell": [
    { label: "Kontenplan", href: "/dashboard/kontenplan", icon: Plus },
  ],
  "/dashboard/review": [
    { label: "Zum Modell", href: "/dashboard/modell", icon: ListChecks },
  ],
  "/dashboard/lernverlauf": [
    { label: "Export", href: "/dashboard/kontoauszug", icon: Download },
  ],
};

/** Longest-prefix match so nested routes inherit their section's actions. */
export function getQuickActions(pathname: string): QuickAction[] {
  const keys = Object.keys(MAP).sort((a, b) => b.length - a.length);
  const key = keys.find((k) => pathname === k || pathname.startsWith(k + "/"));
  return key ? MAP[key] : [];
}
