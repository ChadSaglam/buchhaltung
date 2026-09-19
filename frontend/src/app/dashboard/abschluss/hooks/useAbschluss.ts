import { useCallback, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import type { ExportBatchListResponse, ExportBatchOut, PreflightResponse } from "../types";

const EMPTY_PREFLIGHT: PreflightResponse = {
  exportable: 0,
  total: 0,
  period_from: null,
  period_to: null,
  ready: false,
  blockers: 0,
  checks: [],
};

/** The file endpoints need the bearer token, so a plain <a href> would 401. */
async function download(path: string, filename: string) {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function useAbschluss() {
  const preflight = useApi<PreflightResponse>("/api/export/batches/preflight");
  const batches = useApi<ExportBatchListResponse>("/api/export/batches/");
  const [exporting, setExporting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [packing, setPacking] = useState<number | null>(null);

  const retry = useCallback(() => {
    void preflight.mutate();
    void batches.mutate();
  }, [preflight, batches]);

  const runExport = useCallback(async () => {
    setExporting(true);
    try {
      const res = await api.post<ExportBatchOut>("/api/export/batches/", {});
      const batch = res.data;
      toast.success(`${batch.booking_count} Buchungen exportiert`);
      await download(`/api/export/batches/${batch.id}/file`, batch.filename || `banana_${batch.id}.txt`);
      setConfirming(false);
      await Promise.all([preflight.mutate(), batches.mutate()]);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setExporting(false);
    }
  }, [preflight, batches]);

  const downloadFile = useCallback(async (batch: ExportBatchOut) => {
    try {
      await download(`/api/export/batches/${batch.id}/file`, batch.filename || `banana_${batch.id}.txt`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, []);

  /** B-17: the whole hand-off in one file. Larger than the others, so it says
   *  so while it builds — a silent button that takes twenty seconds reads as
   *  broken. */
  const downloadPack = useCallback(async (batch: ExportBatchOut) => {
    setPacking(batch.id);
    try {
      await download(`/api/export/batches/${batch.id}/pack.zip`, `Treuhand-Export-${batch.id}.zip`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setPacking(null);
    }
  }, []);

  const downloadCover = useCallback(async (batch: ExportBatchOut) => {
    try {
      await download(`/api/export/batches/${batch.id}/cover`, `deckblatt_${batch.id}.txt`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, []);

  return {
    preflight: preflight.data ?? EMPTY_PREFLIGHT,
    batches: batches.data?.items ?? [],
    isLoading: preflight.isLoading,
    error: preflight.error ?? batches.error,
    retry,
    exporting,
    confirming,
    setConfirming,
    runExport,
    downloadFile,
    downloadCover,
    downloadPack,
    packing,
  };
}
