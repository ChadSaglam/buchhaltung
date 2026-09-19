/**
 * Liquidität und Steuerrückstellung (B-71) — the pure bits the card renders.
 *
 * The numbers all come from `/api/liquiditaet/`; nothing is recomputed here.
 * What lives in this file is the wording and the traffic light, because those
 * are the parts worth testing without a browser.
 */
import type { Schemas } from "@/lib/api-schema";
import { formatCHF } from "@/lib/format";

export type LiquiditaetResponse = Schemas["LiquiditaetResponse"];
export type LiquiditaetPosition = Schemas["app__schemas__liquiditaet__PositionOut"];
export type Dauerbuchung = Schemas["app__schemas__liquiditaet__DauerbuchungOut"];
export type Steuer = Schemas["SteuerOut"];
export type Monat = Schemas["MonatOut"];

export type Tone = "success" | "warning" | "danger";

/** Under water at any point in the window is red, however the quarter ends. */
export function liquiditaetTone(report: LiquiditaetResponse | undefined): Tone {
  if (!report) return "success";
  if (report.tiefster_stand < 0) return "danger";
  // A month of the outgoings left over is thin, not safe.
  const monatsbedarf = report.ausgang / 3;
  if (report.tiefster_stand < monatsbedarf) return "warning";
  return "success";
}

export function liquiditaetSatz(report: LiquiditaetResponse | undefined): string {
  if (!report) return "";
  const tief = formatCHF(report.tiefster_stand);
  if (report.tiefster_stand < 0) {
    return `Am ${kurzdatum(report.tiefster_am)} fehlen ${formatCHF(Math.abs(report.tiefster_stand))}.`;
  }
  return `Tiefster Stand ${tief} am ${kurzdatum(report.tiefster_am)}.`;
}

/** "diesen Quartal ~CHF X Steuern zurücklegen" — or why there is no number. */
export function steuerSatz(steuer: Steuer | null | undefined): string {
  if (!steuer) return "";
  if (steuer.satz == null) return "Kein Steuersatz hinterlegt";
  if ((steuer.pro_quartal ?? 0) <= 0) return "Nichts zurückzulegen";
  return `Dieses Quartal ${formatCHF(steuer.pro_quartal)} zurücklegen`;
}

export function kurzdatum(iso: string | null | undefined): string {
  if (!iso) return "–";
  const [y, m, d] = iso.split("T")[0].split("-");
  return y && m && d ? `${d}.${m}.` : iso;
}

export const QUELLE_LABEL: Record<string, string> = {
  debitor: "Kunde zahlt",
  kreditor: "wir zahlen",
  dauerbuchung: "jeden Monat",
};

/** The next few movements, largest impact first within the same day. */
export function naechste(report: LiquiditaetResponse | undefined, limit = 5): LiquiditaetPosition[] {
  return (report?.positionen ?? []).slice(0, limit);
}
