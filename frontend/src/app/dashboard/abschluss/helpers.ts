import { formatCHF, formatDate } from "@/lib/format";
import type { ExportCheck } from "./types";

export type CheckTone = "success" | "danger" | "warning";

/** Green when nothing is wrong; a blocker is red, everything else amber. */
export function checkTone(check: ExportCheck): CheckTone {
  if (check.count === 0) return "success";
  return check.severity === "blocker" ? "danger" : "warning";
}

/** "4 Buchungen" / "1 Buchung" / "" when the check is green. */
export function checkCountLabel(check: ExportCheck): string {
  if (check.count === 0) return "";
  return `${check.count} ${check.count === 1 ? "Buchung" : "Buchungen"}`;
}

/** Blockers first, then warnings — the user fixes top-down. */
export function sortChecks(checks: ExportCheck[]): ExportCheck[] {
  const weight = (c: ExportCheck) => (c.count === 0 ? 2 : c.severity === "blocker" ? 0 : 1);
  return [...checks].sort((a, b) => weight(a) - weight(b));
}

export function formatPeriod(from: string | null | undefined, to: string | null | undefined): string {
  if (!from && !to) return "–";
  if (from === to) return formatDate(from);
  return `${formatDate(from)} – ${formatDate(to)}`;
}

/** What the primary button says — it names the consequence, never "OK". */
export function exportLabel(exportable: number, ready: boolean): string {
  if (exportable === 0) return "Nichts zu exportieren";
  if (!ready) return "Zuerst die roten Punkte korrigieren";
  return `${exportable} ${exportable === 1 ? "Buchung" : "Buchungen"} nach Banana exportieren`;
}

export function batchSubtitle(count: number, total: number): string {
  return `${count} ${count === 1 ? "Buchung" : "Buchungen"} · ${formatCHF(total)}`;
}
