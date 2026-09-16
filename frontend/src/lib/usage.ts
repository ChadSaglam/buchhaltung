/**
 * Verbrauch gegen Plan-Grenzen (B-23) — reine Funktionen, damit sie ohne
 * gerendertes React getestet werden können.
 *
 * `limit === null` heisst *unbegrenzt*. Das ist der einzige Sonderfall, und er
 * kommt in jeder Funktion hier genau einmal vor.
 */

import type { UsageCounter } from "@/lib/api-schema";

export type Ton = "success" | "warning" | "danger" | "neutral";

export function istUnbegrenzt(z: UsageCounter): boolean {
  return z.limit === null || z.limit === undefined;
}

/** 0–100 für den Balken. Unbegrenzt → 0, der Balken wird dann gar nicht gezeigt. */
export function prozent(z: UsageCounter): number {
  if (istUnbegrenzt(z) || z.anteil === null || z.anteil === undefined) return 0;
  return Math.round(Math.min(1, Math.max(0, z.anteil)) * 100);
}

export function ton(z: UsageCounter): Ton {
  if (istUnbegrenzt(z)) return "neutral";
  if (z.erreicht) return "danger";
  if (z.warnung) return "warning";
  return "success";
}

/** "37 von 100" bzw. "37 — unbegrenzt". */
export function verbrauchText(z: UsageCounter): string {
  const einheit = z.key === "speicher_mb" ? " MB" : "";
  if (istUnbegrenzt(z)) return `${z.benutzt}${einheit} — unbegrenzt`;
  return `${z.benutzt}${einheit} von ${z.limit}${einheit}`;
}

export function periodeText(z: UsageCounter): string {
  return z.periode === "monat" ? "in diesem Monat" : "insgesamt";
}

/** Die Zähler, über die die Oberfläche warnen soll — erreichte zuerst. */
export function warnungen(zaehler: UsageCounter[]): UsageCounter[] {
  return zaehler
    .filter((z) => !istUnbegrenzt(z) && (z.warnung || z.erreicht))
    .sort((a, b) => Number(b.erreicht) - Number(a.erreicht));
}

/** Wie der Monat zurückgesetzt wird — für den Fusstext der Seite. */
export function naechsterReset(monatSeit: string): string {
  const start = new Date(monatSeit);
  if (Number.isNaN(start.getTime())) return "—";
  const naechster = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1));
  return naechster.toLocaleDateString("de-CH", { day: "2-digit", month: "long", year: "numeric" });
}
