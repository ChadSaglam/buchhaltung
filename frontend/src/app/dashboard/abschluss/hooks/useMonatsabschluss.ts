import { useCallback, useState } from "react";
import { useApi } from "@/hooks/useApi";
import type { MonthListResponse, MonthReportResponse } from "../types";

const EMPTY_MONTHS: MonthListResponse = { monate: [], labels: {}, aktuell: "" };

/** The month check: pick a month, read the red/green list. Nothing is written. */
export function useMonatsabschluss() {
  const months = useApi<MonthListResponse>("/api/abschluss/monate");
  const [monat, setMonat] = useState<string | null>(null);
  const key = monat ? `/api/abschluss/monat?monat=${monat}` : "/api/abschluss/monat";
  const report = useApi<MonthReportResponse>(key);

  const retry = useCallback(() => {
    void months.mutate();
    void report.mutate();
  }, [months, report]);

  const list = months.data ?? EMPTY_MONTHS;
  return {
    monate: list.monate,
    labels: list.labels,
    selected: monat ?? report.data?.monat ?? list.aktuell,
    setMonat,
    report: report.data,
    isLoading: months.isLoading || report.isLoading,
    error: months.error ?? report.error,
    retry,
  };
}
