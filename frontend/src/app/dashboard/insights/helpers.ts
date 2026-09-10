import type { ParsedQuery } from "@/lib/booking-analytics";

export function chf(n: number) {
  return `CHF ${n.toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const EXAMPLES = [
  "Ausgaben über 500 im Juni",
  "Migros Lebensmittel",
  "Einnahmen 2026",
  "Konto 6500",
];

/** Human-readable chips for every filter the parser recognised in the query. */
export function activeFilterLabels(parsed: ParsedQuery): string[] {
  const f: string[] = [];
  if (parsed.text) f.push(`Text: „${parsed.text}“`);
  if (parsed.minAmount != null) f.push(`≥ ${chf(parsed.minAmount)}`);
  if (parsed.maxAmount != null) f.push(`≤ ${chf(parsed.maxAmount)}`);
  if (parsed.month != null) f.push(`Monat ${parsed.month}`);
  if (parsed.year != null) f.push(`Jahr ${parsed.year}`);
  if (parsed.konto) f.push(`Konto ${parsed.konto}`);
  if (parsed.direction) f.push(parsed.direction === "credit" ? "Einnahmen" : "Ausgaben");
  return f;
}
