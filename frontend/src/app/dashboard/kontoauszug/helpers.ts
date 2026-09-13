import type { TxRow } from "./types";

/** Map an AI confidence score to a badge tone + label. */
export function confidenceTone(c?: number): { tone: "success" | "warning" | "danger" | "neutral"; label: string } {
  if (c == null) return { tone: "neutral", label: "—" };
  const pct = Math.round(c * 100);
  if (c >= 0.8) return { tone: "success", label: `${pct}%` };
  if (c >= 0.5) return { tone: "warning", label: `${pct}%` };
  return { tone: "danger", label: `${pct}%` };
}

/** One classified transaction from `/api/classify/batch` → editable table row. */
export function toRow(r: Record<string, unknown>, i: number): TxRow {
  return {
    Nr: i + 1,
    Datum: (r.datum as string) || "",
    Beschreibung: (r.beschreibung as string) || "",
    KtSoll: (r.kt_soll as string) || "",
    KtHaben: (r.kt_haben as string) || "",
    "Betrag CHF": Number(r.betrag) || 0,
    "MwStUSt-Code": (r.mwst_code as string) || "",
    "MwSt-%": (r.mwst_pct as string) || "",
    "Gebuchte MwStUSt CHF": Number(r.mwst_amount) || 0,
    confidence: typeof r.confidence === "number" ? (r.confidence as number) : undefined,
    source: (r.source as string) || undefined,
    suggSoll: (r.kt_soll as string) || "",
    suggHaben: (r.kt_haben as string) || "",
    accepted: false,
  };
}

/** Payload for `/api/classify/correct`, one per row the user changed (B-45). Unchanged rows teach nothing. */
export function correctionsFor(rows: TxRow[]) {
  return rows
    .filter((r) => r.KtSoll && (r.KtSoll !== r.suggSoll || r.KtHaben !== r.suggHaben))
    .map((r) => ({
      beschreibung: r.Beschreibung,
      original_soll: r.suggSoll ?? "",
      original_haben: r.suggHaben ?? "",
      corrected_soll: r.KtSoll,
      corrected_haben: r.KtHaben,
      corrected_mwst_code: r["MwStUSt-Code"],
      corrected_mwst_pct: r["MwSt-%"],
    }));
}
