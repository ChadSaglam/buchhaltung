import { useCallback, useMemo, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import type { MwstMethode, MwstReportResponse, QuarterListResponse } from "../types";

const EMPTY_QUARTERS: QuarterListResponse = { quartale: [], labels: {}, aktuell: "" };

/** Abschluss › Quartal: Formular 200 from the bookings. Read-only. */
export function useMwst() {
  const quarters = useApi<QuarterListResponse>("/api/abschluss/quartale");
  const [quartal, setQuartal] = useState<string | null>(null);
  const [methode, setMethode] = useState<MwstMethode>("effektiv");
  const [satz, setSatz] = useState("6.5");
  const [copied, setCopied] = useState(false);

  /** One query string for the report and the sheet, stable across renders. */
  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (quartal) params.set("quartal", quartal);
    params.set("methode", methode);
    if (methode === "saldo") params.set("satz", satz);
    return params.toString();
  }, [quartal, methode, satz]);
  const report = useApi<MwstReportResponse>(`/api/abschluss/mwst?${query}`);

  const retry = useCallback(() => {
    void quarters.mutate();
    void report.mutate();
  }, [quarters, report]);

  const copy = useCallback(async () => {
    if (!report.data) return;
    try {
      await navigator.clipboard.writeText(report.data.copy_block);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }, [report.data]);

  /** The sheet needs the bearer token, so it is fetched and saved as a blob. */
  const download = useCallback(async () => {
    if (!report.data) return;
    try {
      const res = await api.get(`/api/abschluss/mwst.txt?${query}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mwst_${report.data.quartal}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, [report.data, query]);

  const list = quarters.data ?? EMPTY_QUARTERS;
  return {
    quartale: list.quartale,
    labels: list.labels,
    selected: quartal ?? report.data?.quartal ?? list.aktuell,
    setQuartal,
    methode,
    setMethode,
    satz,
    setSatz,
    report: report.data,
    isLoading: quarters.isLoading || report.isLoading,
    error: quarters.error ?? report.error,
    retry,
    copy,
    copied,
    download,
  };
}
