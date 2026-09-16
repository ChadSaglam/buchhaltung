import type { PositionRow } from "./types";

/** "1'234.50" — the Swiss way, same as the backend prints it (B-58: shared). */
export { formatAmount as chf } from "@/lib/format";

/** Accepts "1'234.50", "1234,50" and " 12 " — what people actually type. */
export function num(value: string): number {
  const cleaned = (value ?? "").replace(/['\s]/g, "").replace(",", ".");
  const parsed = Number.parseFloat(cleaned);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function zeilenbetrag(row: PositionRow): number {
  return Math.round(num(row.menge) * num(row.einzelpreis) * 100) / 100;
}

export interface Totals {
  netto: number;
  mwst: number;
  total: number;
  satz: number;
}

/** Net from the lines, VAT on top — mirrors services/rechnung.totals_for. */
export function totals(rows: PositionRow[], mwstPct: string): Totals {
  const netto = Math.round(rows.reduce((sum, row) => sum + zeilenbetrag(row), 0) * 100) / 100;
  const satz = Math.abs(num(mwstPct ?? ""));
  if (!satz) return { netto, mwst: 0, total: netto, satz: 0 };
  const total = Math.round(netto * (100 + satz)) / 100;
  return { netto, mwst: Math.round((total - netto) * 100) / 100, total, satz };
}

/** What still keeps the invoice from being written — empty means ready. */
export function fehlendeAngaben(kunde: { name: string }, rows: PositionRow[]): string[] {
  const missing: string[] = [];
  if (!kunde.name.trim()) missing.push("Kundenname");
  const usable = rows.filter((row) => row.bezeichnung.trim() && zeilenbetrag(row) !== 0);
  if (usable.length === 0) missing.push("mindestens eine Position mit Betrag");
  return missing;
}
