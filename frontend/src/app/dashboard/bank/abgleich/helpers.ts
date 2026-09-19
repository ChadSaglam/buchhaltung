import { formatCHF } from "@/lib/format";
import type { AbgleichItem, DocumentOut } from "./types";

/** Why the engine proposed this — the user reads the tier, never the score. */
export const TIER_LABEL: Record<string, string> = {
  referenz: "Referenz stimmt",
  betrag_datum: "Betrag & Datum",
  sammelauftrag: "Sammelauftrag",
  manuell: "Manuell",
};

export const TIER_TONE: Record<string, "success" | "warning" | "info" | "neutral"> = {
  referenz: "success",
  betrag_datum: "info",
  sammelauftrag: "warning",
  manuell: "neutral",
};

/** A reference hit is a fact — it may be confirmed without reading anything else. */
export function isCertain(item: AbgleichItem): boolean {
  return item.tier === "referenz";
}

export function documentTotal(item: AbgleichItem): number {
  return round2(item.documents.reduce((sum, d) => sum + (d.amount ?? 0), 0));
}

export function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Sum of the invoices the user ticked in the manual picker. */
export function selectedTotal(documents: DocumentOut[], selected: Set<number>): number {
  return round2(documents.filter((d) => selected.has(d.id)).reduce((sum, d) => sum + (d.amount ?? 0), 0));
}

/**
 * What to tell the user about a manual selection: matching sums are the happy
 * path, a difference is allowed but must be visible before they book it.
 */
export function differenceHint(lineAmount: number, selectedSum: number): { ok: boolean; text: string } {
  const line = round2(Math.abs(lineAmount));
  const diff = round2(selectedSum - line);
  if (selectedSum === 0) return { ok: false, text: "Keine Rechnung ausgewählt" };
  if (diff === 0) return { ok: true, text: "Summe stimmt genau" };
  const word = diff > 0 ? "mehr" : "weniger";
  return { ok: false, text: `${formatCHF(Math.abs(diff))} ${word} als die Bankzeile` };
}
