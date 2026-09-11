"use client";
import { useEffect } from "react";
import { getLocale } from "@/lib/i18n";

/**
 * Keeps `<html lang>` in step with the i18n locale (B-19). The server renders
 * `lang="de"`; the stored locale is only known in the browser, so it is
 * applied after hydration and again whenever `setLocale()` runs.
 */
export function LangSync() {
  useEffect(() => {
    document.documentElement.lang = getLocale();
  }, []);
  return null;
}
