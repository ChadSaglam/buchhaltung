/**
 * Offene Posten (B-65) — the pure part: how overdue reads, what the next
 * Mahnung is called, and which rows deserve the owner's attention first.
 */
import type { Schemas } from "@/lib/api-schema";

export type OffenePostenResponse = Schemas["OffenePostenResponse"];
export type SideOut = Schemas["SideOut"];
export type OpenItemOut = Schemas["OpenItemOut"];
export type MahnungDraft = Schemas["MahnungDraft"];

export const BUCKET_LABEL: Record<string, string> = {
  nicht_faellig: "Noch nicht fällig",
  "1_30": "1–30 Tage",
  "31_60": "31–60 Tage",
  "61_90": "61–90 Tage",
  ueber_90: "Über 90 Tage",
};

export const STUFE_LABEL: Record<number, string> = {
  1: "Zahlungserinnerung",
  2: "1. Mahnung",
  3: "Letzte Mahnung",
};

/** Plain words instead of a number: what the owner reads in the row. */
export function overdueLabel(days: number): string {
  if (days <= 0) return "Noch nicht fällig";
  if (days === 1) return "1 Tag überfällig";
  return `${days} Tage überfällig`;
}

/** Green while it is not due, amber in the first month, red after that. */
export function overdueTone(days: number): "success" | "warning" | "danger" {
  if (days <= 0) return "success";
  return days <= 30 ? "warning" : "danger";
}

/** What the Mahnung button says — it names the stage that would go out. */
export function mahnungLabel(mahnstufe: number): string {
  const next = Math.min(3, (mahnstufe || 0) + 1);
  return STUFE_LABEL[next];
}

/** "2. Mahnung am 01.09.2026" — empty when none has gone out yet. */
export function mahnungHistory(item: OpenItemOut): string {
  const stufe = item.document.mahnstufe ?? 0;
  if (!stufe) return "";
  const sent = item.document.mahnung_sent_at;
  const day = sent ? new Date(sent).toLocaleDateString("de-CH") : "";
  return day ? `${STUFE_LABEL[stufe]} am ${day}` : STUFE_LABEL[stufe];
}

/** The rows worth showing in a widget: overdue first, capped. */
export function urgentItems(side: SideOut | undefined, limit = 4): OpenItemOut[] {
  return (side?.items ?? []).slice(0, limit);
}

/** Non-empty aging buckets, in the order the backend defines them. */
export function bucketRows(side: SideOut | undefined): { key: string; label: string; amount: number }[] {
  const buckets = side?.buckets ?? {};
  return Object.keys(BUCKET_LABEL)
    .filter((key) => (buckets[key] ?? 0) !== 0)
    .map((key) => ({ key, label: BUCKET_LABEL[key], amount: buckets[key] ?? 0 }));
}
