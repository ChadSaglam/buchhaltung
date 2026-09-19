/**
 * Dauerbuchungen (B-74) — the pure parts.
 *
 * Everything comes from `/api/dauerbuchungen/`; nothing is recomputed here.
 * What lives in this file is the wording and the traffic light, which are the
 * parts worth testing without a browser.
 */
import type { Schemas } from "@/lib/api-schema";
import { formatCHF } from "@/lib/format";

export type DauerbuchungenResponse = Schemas["DauerbuchungenResponse"];
export type Dauerbuchung = Schemas["app__schemas__dauerbuchungen__DauerbuchungOut"];

export type DauerStatus = "bezahlt" | "offen" | "fehlt";

export const STATUS_LABEL: Record<DauerStatus, string> = {
  bezahlt: "bezahlt",
  offen: "kommt noch",
  fehlt: "fehlt",
};

export const STATUS_TONE: Record<DauerStatus, "success" | "neutral" | "warning"> = {
  bezahlt: "success",
  offen: "neutral",
  fehlt: "warning",
};

/** "Cembra 770.60 fehlt diesen Monat" — the sentence this feature exists for. */
export function fehltSatz(entry: Dauerbuchung): string {
  const tage = entry.tage_ueberfaellig ?? 0;
  const seit = tage === 1 ? "seit einem Tag" : `seit ${tage} Tagen`;
  return `${entry.label} ${formatCHF(entry.betrag)} fehlt diesen Monat (${seit}).`;
}

/** The card's headline: what still has to leave the account, or that nothing does. */
export function kopfzeile(data: DauerbuchungenResponse | undefined): string {
  if (!data) return "";
  const fehlen = data.fehlen ?? [];
  if (fehlen.length > 0) {
    return fehlen.length === 1
      ? `1 Zahlung fehlt: ${formatCHF(fehlen[0].betrag)}`
      : `${fehlen.length} Zahlungen fehlen: ${formatCHF(fehlen.reduce((sum, e) => sum + e.betrag, 0))}`;
  }
  if ((data.offen_total ?? 0) > 0) return `${formatCHF(data.offen_total)} gehen diesen Monat noch raus`;
  if ((data.eintraege ?? []).length === 0) return "Noch keine wiederkehrenden Zahlungen erkannt";
  return "Alles bezahlt diesen Monat";
}

export function kopfTone(data: DauerbuchungenResponse | undefined): "success" | "warning" | "neutral" {
  if (!data || (data.eintraege ?? []).length === 0) return "neutral";
  if ((data.fehlen ?? []).length > 0) return "warning";
  return (data.offen_total ?? 0) > 0 ? "neutral" : "success";
}

/** "am 5." — the day of the month, in the short form a German sentence wants. */
export function tagLabel(entry: Dauerbuchung): string {
  return `am ${entry.tag}.`;
}
