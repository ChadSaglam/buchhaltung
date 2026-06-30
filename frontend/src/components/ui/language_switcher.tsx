"use client";
import { useState, useEffect } from "react";
import { getLocale, setLocale, getAvailableLocales, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LanguageSwitcher({ className }: { className?: string }) {
  const [locale, setCurrentLocale] = useState<Locale>("de");
  useEffect(() => {
    setCurrentLocale(getLocale());
  }, []);

  const handleChange = (newLocale: Locale) => {
    setLocale(newLocale);
    setCurrentLocale(newLocale);
    window.location.reload();
  };

  return (
    <div className={cn("flex items-center gap-0.5 rounded-lg bg-muted p-0.5", className)}>
      {getAvailableLocales().map((l) => (
        <button
          key={l.code}
          onClick={() => handleChange(l.code)}
          aria-pressed={locale === l.code}
          className={cn(
            "rounded-md px-2 py-1 text-xs font-semibold uppercase transition-colors",
            locale === l.code
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {l.code}
        </button>
      ))}
    </div>
  );
}
