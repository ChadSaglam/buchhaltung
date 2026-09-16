/**
 * Lohn (B-72) — the pure parts.
 *
 * Every number comes from `/api/lohn/*`; nothing is recomputed here. What lives
 * in this file is the wording, the month names and the one judgement the UI has
 * to make on its own: whether payroll is usable at all yet, and what to tell the
 * owner when it is not.
 *
 * That judgement matters more than it looks. The backend refuses a payslip when
 * a rate is missing, so the only way the user ever sees an error is by pressing
 * a button that was never going to work. The page therefore blocks first and
 * says which rate is missing, in the order the payslip needs them.
 */
import type { Schemas } from "@/lib/api-schema";
import { formatCHF } from "@/lib/format";

export type LohnSettings = Schemas["LohnSettingsOut"];
export type Mitarbeiter = Schemas["MitarbeiterOut"];
export type Lohnlauf = Schemas["LohnlaufOut"];
export type Abzug = Schemas["AbzugOut"];
export type AbrechnungListItem = Schemas["AbrechnungListItem"];

export const MONATE = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
] as const;

export function monatsname(monat: number): string {
  return MONATE[monat - 1] ?? String(monat);
}

export function periodeLabel(jahr: number, monat: number): string {
  return `${monatsname(monat)} ${jahr}`;
}

/** The compulsory rates, in payslip order, with the wording the form uses. */
export const PFLICHTSAETZE = [
  { feld: "uvg_nbu_satz", label: "UVG NBU", hinweis: "Nichtberufsunfall — zahlt der Arbeitnehmer" },
  { feld: "uvg_bu_satz", label: "UVG BU", hinweis: "Berufsunfall — zahlt der Arbeitgeber" },
  { feld: "fak_satz", label: "FAK", hinweis: "Familienausgleichskasse, kantonal" },
  { feld: "verwaltungskosten_satz", label: "Verwaltungskosten", hinweis: "Beitrag der Ausgleichskasse" },
] as const;

/** Voluntary — absent means *not insured*, which is an answer and not a gap. */
export const FREIWILLIGE_SAETZE = [
  { feld: "uvgz_satz_an", label: "UVGZ Arbeitnehmer" },
  { feld: "uvgz_satz_ag", label: "UVGZ Arbeitgeber" },
  { feld: "ktg_satz_an", label: "KTG Arbeitnehmer" },
  { feld: "ktg_satz_ag", label: "KTG Arbeitgeber" },
] as const;

/** What the owner is told before they can run payroll at all. */
export function bereitschaftSatz(settings: LohnSettings | undefined): string {
  if (!settings) return "";
  const fehlt = settings.fehlt ?? [];
  if (fehlt.length === 0) return "Bereit — die Sätze sind hinterlegt.";
  return fehlt.length === 1
    ? `Noch nicht bereit. Es fehlt: ${fehlt[0]}.`
    : `Noch nicht bereit. Es fehlen: ${fehlt.join(", ")}.`;
}

export function bereitschaftTone(settings: LohnSettings | undefined): "success" | "warning" {
  return settings && (settings.fehlt ?? []).length === 0 ? "success" : "warning";
}

/**
 * The line above the "signed off" switch.
 *
 * Deliberately not reassuring. Until somebody has compared one real month with
 * what the previous payroll produced, the arithmetic being right says nothing
 * about the setup being right, and that is what the watermark is for.
 */
export function freigabeSatz(settings: LohnSettings | undefined): string {
  if (!settings) return "";
  if (settings.freigegeben) return "Freigegeben — die Abrechnungen werden ohne Wasserzeichen gedruckt.";
  return `Noch nicht freigegeben. Jede Abrechnung trägt "${settings.wasserzeichen}".`;
}

/** "5.30 %", or nothing at all for a fixed amount like BVG. */
export function satzLabel(satz: number | null | undefined): string {
  return satz ? `${satz.toFixed(2)} %` : "";
}

/** "" → null (clears a voluntary rate); "1,6" → 1.6; nonsense → null. */
export function satzWert(raw: string): number | null {
  const cleaned = (raw ?? "").replace(",", ".").trim();
  if (!cleaned) return null;
  const parsed = Number.parseFloat(cleaned);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) return null;
  return Math.round(parsed * 10000) / 10000;
}

/** "" → null (no amount on file); "300.50" → 300.5. */
export function betragWert(raw: string): number | null {
  const cleaned = (raw ?? "").replace(/'/g, "").replace(",", ".").trim();
  if (!cleaned) return null;
  const parsed = Number.parseFloat(cleaned);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return Math.round(parsed * 100) / 100;
}

/** A part month is the thing people query first, so the payslip says it out loud. */
export function anteilSatz(lauf: Lohnlauf | undefined): string {
  if (!lauf || lauf.anteil >= 1) return "";
  const prozent = Math.round(lauf.anteil * 100);
  return `Teilmonat — ${prozent} % (Ein- oder Austritt im Monat).`;
}

export function nettoSatz(lauf: Lohnlauf | undefined): string {
  if (!lauf) return "";
  return `${formatCHF(lauf.brutto)} brutto − ${formatCHF(lauf.abzuege_total)} Abzüge = ${formatCHF(lauf.netto)} netto`;
}

export function istAbgerechnet(lauf: Lohnlauf | undefined): boolean {
  return Boolean(lauf?.abrechnung_id);
}

/** Employees with no exit date, or whose exit is still ahead of `stichtag`. */
export function aktive(liste: Mitarbeiter[], stichtag: string): Mitarbeiter[] {
  return liste.filter((m) => !m.austritt || m.austritt >= stichtag);
}

export function anzeigeName(person: Mitarbeiter | undefined): string {
  if (!person) return "";
  return person.anzeige_name || `${person.vorname} ${person.name}`.trim() || `Mitarbeiter ${person.id}`;
}

/** Last day of a month, ISO — what `aktive()` compares an exit date against. */
export function monatsende(jahr: number, monat: number): string {
  const tag = new Date(Date.UTC(jahr, monat, 0)).getUTCDate();
  return `${jahr}-${String(monat).padStart(2, "0")}-${String(tag).padStart(2, "0")}`;
}
