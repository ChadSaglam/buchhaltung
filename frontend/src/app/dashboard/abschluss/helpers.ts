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

/** "April 2026" from the key, so the picker reads the same as the report. */
export function monthLabel(monat: string, labels: Record<string, string>): string {
  return labels[monat] ?? monat;
}

/** The one line that says whether the month is closed. */
export function monthVerdict(blockers: number, warnings: number): { tone: "success" | "danger" | "warning"; text: string } {
  if (blockers > 0) {
    return { tone: "danger", text: `${blockers} ${blockers === 1 ? "Punkt" : "Punkte"} blockieren den Abschluss` };
  }
  if (warnings > 0) {
    return { tone: "warning", text: `Abschluss möglich · ${warnings} ${warnings === 1 ? "Hinweis" : "Hinweise"}` };
  }
  return { tone: "success", text: "Monat ist sauber abgeschlossen" };
}

/** The bank-vs-1020 difference in the words the owner needs. */
export function differenceText(differenz: number): string {
  if (Math.abs(differenz) < 0.005) return "Bank und Konto 1020 stimmen";
  const richtung = differenz > 0 ? "mehr auf der Bank als gebucht" : "mehr gebucht als auf der Bank";
  return `${formatCHF(Math.abs(differenz))} ${richtung}`;
}

/** The Ziffern the form sums up — bold in the table, so the eye finds them. */
export const MWST_TOTAL_ZIFFERN = new Set(["289", "299", "399", "479", "500", "510"]);

/** The one sentence the owner needs: pay, get back, or nothing. */
export function mwstVerdict(zuBezahlen: number, guthaben: number): { tone: "danger" | "success" | "neutral"; text: string } {
  if (zuBezahlen > 0) return { tone: "danger", text: `${formatCHF(zuBezahlen)} zu bezahlen` };
  if (guthaben > 0) return { tone: "success", text: `${formatCHF(guthaben)} Guthaben` };
  return { tone: "neutral", text: "Nichts zu bezahlen" };
}

/** Ziffern with no booking behind them are shown but greyed — they need a human. */
export function isEmptyZiffer(row: { umsatz?: number | null; steuer?: number | null }): boolean {
  return (row.umsatz ?? 0) === 0 && (row.steuer ?? 0) === 0;
}

export function methodeLabel(methode: string, satz: number | null | undefined): string {
  if (methode === "saldo") return `Saldosteuersatz${satz ? ` ${satz.toFixed(1)} %` : ""}`;
  return "Effektive Methode";
}
