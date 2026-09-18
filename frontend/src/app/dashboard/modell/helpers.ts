import type { VisionStatus } from "./types";
import type { DownloadType, MemoryEntry } from "./types";

export function accuracyBarClass(acc: number) {
  if (acc >= 0.85) return "bg-success";
  if (acc >= 0.6) return "bg-warning";
  return "bg-destructive";
}

export function accuracyTextClass(acc: number) {
  if (acc >= 0.85) return "text-success";
  if (acc >= 0.6) return "text-warning";
  return "text-destructive";
}

export function formatDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-CH", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export const IMPORT_EXTENSIONS = [".xls", ".xlsx", ".csv"];

export function fileExtension(name: string) {
  return name.substring(name.lastIndexOf(".")).toLowerCase();
}

export function downloadFilename(type: DownloadType, now: Date = new Date()) {
  const ext = type === "bundle" ? "zip" : type === "model" ? "pkl" : "json";
  return `buchhaltung_${type}_${now.toISOString().slice(0, 16).replace(/[:-]/g, "")}.${ext}`;
}

export function filterMemory(entries: MemoryEntry[], filter: string) {
  return entries.filter(e =>
    !filter || (e.lookup_key ?? "").toLowerCase().includes(filter.toLowerCase())
  );
}

/**
 * B-88: what the Genauigkeit figure actually measures — one sentence, one place.
 *
 * It is a cross-validation over the tenant's own *booking* descriptions: short,
 * clean, bank-shaped strings like `Agrola, TS`. What the scanner hands the
 * classifier is OCR off a till receipt — `LANDI THULA TopShop Matzingen BLEIFREI
 * 95`. Different length, different vocabulary, different distribution. Measured
 * on the first real run (762 of the owner's 2024 bookings): `Agrola, TS` →
 * Gedächtnis, 6210, 100 %. The real receipt line → the ML's own top-5 put the
 * *wrong* account first at 22 %; the keyword rule rescued it at 72 %.
 *
 * The pipeline works as designed. The problem was that the number the page leads
 * with belongs to a layer that was not consulted, and the page did not say so.
 */
export const GENAUIGKEIT_BASIS = "Cross-Validation auf Buchungstexten";
export const GENAUIGKEIT_ERKLAERUNG =
  "Gemessen an Buchungstexten, wie sie im Kontoauszug stehen (z. B. «Agrola, TS»). " +
  "Was der Scanner von einem Kassenbon liest, sieht anders aus — dort tragen " +
  "Gedächtnis und Regeln den grössten Teil. Diese Zahl sagt nichts über Belege.";

export function isOverfit(trainAccuracy: number, acc: number) {
  return trainAccuracy > 0 && acc > 0 && trainAccuracy - acc > 0.15;
}

/**
 * A scanner can read a receipt two ways: an Ollama vision model, or the
 * built-in OCR. Either one counts — reporting "Nicht verbunden" while the
 * custom OCR is happily reading invoices is what this card used to do.
 */
export function visionAktiv(vision: VisionStatus): boolean {
  return Boolean(vision.best_vision) || Boolean(vision.custom_ocr_available);
}
