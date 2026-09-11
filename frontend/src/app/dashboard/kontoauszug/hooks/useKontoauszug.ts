import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { toRow } from "../helpers";
import type { ExportFormat, TxRow } from "../types";

export function useKontoauszug() {
  const [phase, setPhase] = useState<"idle" | "parsing" | "classifying">("idle");
  const [rows, setRows] = useState<TxRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // The failed upload, kept so "Erneut versuchen" can re-run the same file.
  const [failure, setFailure] = useState<{ error: unknown; file: File } | null>(null);
  // Storage key of the uploaded statement (B-09); saved on every booking it produces.
  const [sourceKey, setSourceKey] = useState<string | null>(null);

  const processFile = async (file: File) => {
    setPhase("parsing"); setRows([]); setSaved(false); setSourceKey(null); setFailure(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const parseRes = await api.post("/api/pdf/parse", form);
      setSourceKey(parseRes.data.source_key ?? null);

      setPhase("classifying");
      const classRes = await api.post("/api/classify/batch", { transactions: parseRes.data.transactions || [] });
      setRows((classRes.data.results || []).map(toRow));
    } catch (e) {
      setFailure({ error: e, file });
    } finally {
      setPhase("idle");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post("/api/bookings/", rows.map((r) => ({
        datum: r.Datum, beschreibung: r.Beschreibung, betrag: r["Betrag CHF"],
        kt_soll: r.KtSoll, kt_haben: r.KtHaben, mwst_code: r["MwStUSt-Code"],
        mwst_pct: r["MwSt-%"], mwst_amount: r["Gebuchte MwStUSt CHF"], source: "kontoauszug",
        source_key: sourceKey,
      })));
      for (const r of rows) {
        if (r.KtSoll) await api.post("/api/classify/correct", {
          beschreibung: r.Beschreibung, original_soll: r.KtSoll, original_haben: r.KtHaben,
          corrected_soll: r.KtSoll, corrected_haben: r.KtHaben,
        }).catch(() => {});
      }
      setSaved(true);
      toast.success("Buchungen gespeichert");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async (format: ExportFormat) => {
    try {
      const res = await api.get(`/api/export/${format}`, { params: { source: "kontoauszug" }, responseType: "blob" });
      const ext = format === "banana" ? "txt" : format === "excel" ? "xlsx" : "csv";
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `buchhaltung.${ext}`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const updateRow = (idx: number, field: keyof TxRow, value: string | number) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  const accept = (r: TxRow): TxRow => ({ ...r, KtSoll: r.suggSoll ?? r.KtSoll, KtHaben: r.suggHaben ?? r.KtHaben, accepted: true });
  const acceptSuggestion = (idx: number) => setRows((prev) => prev.map((r, i) => (i === idx ? accept(r) : r)));
  const acceptAll = () => setRows((prev) => prev.map(accept));
  const reset = () => { setRows([]); setSaved(false); setFailure(null); };
  const retry = () => failure && processFile(failure.file);

  return {
    phase, rows, saving, saved, failure, sourceKey,
    processFile, handleSave, handleExport, updateRow, acceptSuggestion, acceptAll, reset, retry,
  };
}
