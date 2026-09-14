import type { DocumentOut, DocumentStatus } from "./types";

export const STATUS_LABEL: Record<DocumentStatus, string> = {
  offen: "Offen",
  bezahlt: "Bezahlt",
  exportiert: "Exportiert",
  fehler: "Fehler",
};

export const STATUS_TONE: Record<DocumentStatus, "warning" | "success" | "info" | "danger"> = {
  offen: "warning",
  bezahlt: "success",
  exportiert: "info",
  fehler: "danger",
};

/** Where the facts came from, for the row's badge title. */
export function sourceLabel(source: string): string {
  switch (source) {
    case "qr":
      return "QR-Rechnung (exakt)";
    case "vision":
      return "Vision-Modell";
    case "ocr":
      return "OCR";
    case "manual":
      return "Manuell";
    default:
      return "–";
  }
}

/** "CHF 1'949.45" — hand-rolled so node, Safari and Chrome agree on the apostrophe. */
export function formatCHF(amount: number | null | undefined, currency = "CHF"): string {
  if (amount == null || !Number.isFinite(amount)) return "–";
  const sign = amount < 0 ? "-" : "";
  const [int, frac] = Math.abs(amount).toFixed(2).split(".");
  return `${currency} ${sign}${int.replace(/\B(?=(\d{3})+(?!\d))/g, "'")}.${frac}`;
}

/** DD.MM.YYYY from an ISO date, "–" when unknown. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const [y, m, d] = iso.split("-");
  return y && m && d ? `${d}.${m}.${y}` : iso;
}

export function isOverdue(doc: DocumentOut, today = new Date()): boolean {
  if (doc.status !== "offen" || !doc.due_date) return false;
  return new Date(doc.due_date + "T00:00:00") < new Date(today.toDateString());
}

/** Sort: errors first (they need a hand), then open by due date, then the rest newest first. */
export function sortDocuments(docs: DocumentOut[]): DocumentOut[] {
  const rank: Record<string, number> = { fehler: 0, offen: 1, bezahlt: 2, exportiert: 3 };
  return [...docs].sort((a, b) => {
    const r = (rank[a.status] ?? 9) - (rank[b.status] ?? 9);
    if (r !== 0) return r;
    if (a.status === "offen" && b.status === "offen") {
      const da = a.due_date ?? "9999";
      const db = b.due_date ?? "9999";
      if (da !== db) return da < db ? -1 : 1;
    }
    return b.id - a.id;
  });
}
