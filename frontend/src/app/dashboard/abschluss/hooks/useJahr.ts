import { useCallback, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import type { JahrReportResponse, YearListResponse } from "../types";

/** The file endpoints need the bearer token, so a plain <a href> would 401. */
async function download(path: string, filename: string) {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** Abschluss › Jahr: Bilanz, Erfolgsrechnung, Abschreibungen — read-only (B-70). */
export function useJahr() {
  const years = useApi<YearListResponse>("/api/abschluss/jahre");
  const [jahr, setJahr] = useState<number | null>(null);
  const [busy, setBusy] = useState<"pdf" | "zip" | null>(null);

  const report = useApi<JahrReportResponse>(`/api/abschluss/jahr${jahr ? `?jahr=${jahr}` : ""}`);

  const retry = useCallback(() => {
    void years.mutate();
    void report.mutate();
  }, [years, report]);

  const holen = useCallback(
    async (was: "pdf" | "zip") => {
      const aktuell = report.data?.jahr ?? jahr ?? years.data?.aktuell;
      if (!aktuell) return;
      setBusy(was);
      try {
        await download(
          `/api/abschluss/jahr.${was}?jahr=${aktuell}`,
          `jahresabschluss-${aktuell}.${was}`,
        );
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        setBusy(null);
      }
    },
    [jahr, report.data, years.data],
  );

  return {
    jahre: years.data?.jahre ?? [],
    jahr: report.data?.jahr ?? jahr ?? years.data?.aktuell ?? null,
    setJahr,
    report: report.data,
    isLoading: years.isLoading || report.isLoading,
    error: years.error ?? report.error,
    retry,
    busy,
    pdfHolen: () => holen("pdf"),
    paketHolen: () => holen("zip"),
  };
}
