import { useCallback, useMemo, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import { sortDocuments } from "../helpers";
import type { DocumentOut, DocumentStatus, DocumentSummary, UploadResponse } from "../types";

interface ListResponse {
  items: DocumentOut[];
  count: number;
}

export function useRechnungen() {
  const list = useApi<ListResponse>("/api/documents/");
  const summary = useApi<DocumentSummary>("/api/documents/summary");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [filter, setFilter] = useState<DocumentStatus | "alle">("alle");

  const items = useMemo(() => {
    const all = sortDocuments(list.data?.items ?? []);
    return filter === "alle" ? all : all.filter((d) => d.status === filter);
  }, [list.data, filter]);

  const refresh = useCallback(() => Promise.all([list.mutate(), summary.mutate()]), [list, summary]);

  // Files go up in batches of 5 so a 50-file drop shows progress and one bad batch does not lose the rest.
  const upload = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      setUploading(true);
      setProgress({ done: 0, total: files.length });
      let created = 0;
      let failed = 0;
      try {
        for (let i = 0; i < files.length; i += 5) {
          const batch = files.slice(i, i + 5);
          const form = new FormData();
          batch.forEach((f) => form.append("files", f));
          try {
            const res = await api.post<UploadResponse>("/api/documents/", form);
            created += res.data.created;
            failed += res.data.failed;
          } catch (e) {
            failed += batch.length;
            toast.error(errorMessage(e));
          }
          setProgress({ done: Math.min(i + 5, files.length), total: files.length });
          await refresh();
        }
        if (created) toast.success(`${created} Rechnung${created === 1 ? "" : "en"} erfasst`);
        if (failed) toast.error(`${failed} Datei${failed === 1 ? "" : "en"} nicht erkannt — siehe Status „Fehler“`);
      } finally {
        setUploading(false);
        setProgress(null);
      }
    },
    [refresh],
  );

  // Optimistic status change with rollback (same pattern as the review queue).
  const setStatus = useCallback(
    async (doc: DocumentOut, status: DocumentStatus) => {
      const before = list.data;
      if (!before) return;
      await list.mutate(
        { ...before, items: before.items.map((d) => (d.id === doc.id ? { ...d, status } : d)) },
        { revalidate: false },
      );
      try {
        await api.patch(`/api/documents/${doc.id}`, { status });
        await summary.mutate();
      } catch (e) {
        await list.mutate(before, { revalidate: false });
        toast.error(errorMessage(e));
      }
    },
    [list, summary],
  );

  /**
   * B-89: "die war schon bezahlt". Same optimistic pattern as the status change,
   * because it is the same kind of claim — it decides whether this row is money
   * we still owe.
   */
  const setPaidAtSource = useCallback(
    async (doc: DocumentOut, paid: boolean) => {
      const before = list.data;
      if (!before) return;
      await list.mutate(
        { ...before, items: before.items.map((d) => (d.id === doc.id ? { ...d, paid_at_source: paid } : d)) },
        { revalidate: false },
      );
      try {
        await api.patch(`/api/documents/${doc.id}`, { paid_at_source: paid });
        await summary.mutate();
      } catch (e) {
        await list.mutate(before, { revalidate: false });
        toast.error(errorMessage(e));
      }
    },
    [list, summary],
  );

  return {
    items,
    summary: summary.data,
    isLoading: list.isLoading,
    error: list.error,
    retry: refresh,
    filter,
    setFilter,
    upload,
    uploading,
    progress,
    setStatus,
    setPaidAtSource,
  };
}
