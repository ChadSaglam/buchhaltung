"use client";
import { useState, useEffect } from "react";
import { getLocale, getAvailableLocales, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * Language switcher — intentionally VISIBLE BUT DISABLED for now.
 *
 * Multi-language UI is on the roadmap but not shipped, so the control renders
 * as a read-only pill group showing the active locale with a "bald verfügbar"
 * (coming soon) hint. Wiring locale switching back on is a matter of
 * re-enabling the buttons and calling setLocale — see Settings › Darstellung
 * for the matching disabled row.
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const [locale, setCurrentLocale] = useState<Locale>("de");
  useEffect(() => {
    setCurrentLocale(getLocale());
  }, []);

  return (
    <div
      className={cn("group relative flex items-center", className)}
      title="Mehrsprachigkeit — bald verfügbar"
    >
      <div
        aria-disabled="true"
        className="flex cursor-not-allowed items-center gap-0.5 rounded-lg bg-muted p-0.5 opacity-70"
      >
        {getAvailableLocales().map((l) => (
          <span
            key={l.code}
            aria-current={locale === l.code}
            className={cn(
              "rounded-md px-2 py-1 text-xs font-semibold uppercase transition-colors select-none",
              locale === l.code
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground/70"
            )}
          >
            {l.code}
          </span>
        ))}
      </div>
      {/* Coming-soon tooltip on hover/focus */}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-card px-2 py-1 text-[11px] font-medium text-muted-foreground opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100"
      >
        Mehrsprachigkeit — bald verfügbar
      </span>
    </div>
  );
}
