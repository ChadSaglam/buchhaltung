"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { tabsFor } from "@/lib/navigation";
import { cn } from "@/lib/utils";

/**
 * The tab row of a surface (`docs/IA-2026-09-14.md`).
 *
 * Rechnungen, Scanner and der E-Mail-Eingang used to be three sidebar entries;
 * they are three tabs of *Belege*. Same for Kontoauszug, Abgleich and Buchungen
 * under *Bank*. Rendering nothing on a surface without tabs keeps Heute and
 * Abschluss (which have their own in-page tabs) exactly as they were.
 */
export function SurfaceTabs() {
  const pathname = usePathname();
  const { tabs, active, surface } = tabsFor(pathname);
  if (!surface || tabs.length === 0) return null;

  return (
    <div className="mb-6 border-b border-border">
      <p className="mb-2 text-xs text-muted-foreground">{surface.frage}</p>
      <nav aria-label={`${surface.label} — Bereiche`} className="-mb-px flex gap-1 overflow-x-auto">
        {tabs.map((tab) => {
          const current = tab.href === active?.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={current ? "page" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                current
                  ? "border-brand-600 text-brand-600 dark:border-brand-300 dark:text-brand-300"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <tab.icon className="h-4 w-4" aria-hidden="true" />
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
