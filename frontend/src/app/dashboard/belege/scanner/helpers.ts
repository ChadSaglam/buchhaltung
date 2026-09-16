import { Bot, Brain, ClipboardList, type LucideIcon } from "lucide-react";

export function calcMwst(betrag: number, pct: string): number {
  if (!pct || !betrag) return 0;
  const p = Math.abs(parseFloat(pct));
  const val = (betrag * p) / (100 + p);
  return parseFloat(pct) < 0 ? -Math.round(val * 100) / 100 : Math.round(val * 100) / 100;
}

/**
 * Which icon stands for a classification source (B-58: was 🧠/🤖/📋).
 * Emoji render differently on every platform and screen readers announce them
 * by name — a Lucide glyph plus a real label does not.
 */
export function sourceIcon(source: string): { Icon: LucideIcon; label: string } {
  if (source === "Gedächtnis") return { Icon: Brain, label: "aus dem Gedächtnis" };
  if (source === "ML") return { Icon: Bot, label: "vom Modell" };
  return { Icon: ClipboardList, label: "aus Regeln" };
}

/** B-58: one formatter for the whole app — see `lib/format.ts`. */
export { formatCHF } from "@/lib/format";
