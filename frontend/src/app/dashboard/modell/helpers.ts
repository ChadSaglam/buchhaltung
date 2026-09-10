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

export function formatDate(iso: string) {
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

export function isOverfit(trainAccuracy: number, acc: number) {
  return trainAccuracy > 0 && acc > 0 && trainAccuracy - acc > 0.15;
}
