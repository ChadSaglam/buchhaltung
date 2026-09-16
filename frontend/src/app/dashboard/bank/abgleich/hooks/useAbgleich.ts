import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import { inboxKeyFor, moveSelection, selectionAfterRemove } from "@/lib/inbox-keys";
import type { AbgleichResponse } from "../types";

const EMPTY: AbgleichResponse = {
  items: [],
  open_transactions: [],
  open_documents: [],
  summary: { vorschlaege: 0, offene_zeilen: 0, offene_dokumente: 0, exakt: 0 },
};

export function useAbgleich() {
  const inbox = useApi<AbgleichResponse>("/api/abgleich/");
  const [selected, setSelected] = useState(-1);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const data = inbox.data ?? EMPTY;
  const items = useMemo(() => data.items, [data]);

  const refresh = useCallback(() => inbox.mutate(), [inbox]);

  /** Optimistic: the decided row leaves at once and comes back if the server refuses. */
  const decide = useCallback(
    async (transactionId: number, action: "confirm" | "reject" | "ignore") => {
      const before = inbox.data;
      if (!before) return;
      const index = before.items.findIndex((i) => i.transaction.id === transactionId);
      setBusy(transactionId);
      setSelected((s) => (index >= 0 ? selectionAfterRemove(s, index, before.items.length) : s));
      await inbox.mutate(
        {
          ...before,
          items: before.items.filter((i) => i.transaction.id !== transactionId),
          open_transactions: before.open_transactions.filter((t) => t.id !== transactionId),
        },
        { revalidate: false },
      );
      try {
        await api.post(`/api/abgleich/${transactionId}/${action}`);
        if (action === "confirm") toast.success("Gebucht");
        await inbox.mutate();
      } catch (e) {
        await inbox.mutate(before, { revalidate: false });
        if (index >= 0) setSelected(index);
        toast.error(errorMessage(e));
      } finally {
        setBusy(null);
      }
    },
    [inbox],
  );

  const confirm = useCallback((id: number) => decide(id, "confirm"), [decide]);
  const reject = useCallback((id: number) => decide(id, "reject"), [decide]);
  const ignore = useCallback((id: number) => decide(id, "ignore"), [decide]);

  const matchManually = useCallback(
    async (transactionId: number, documentIds: number[]) => {
      setBusy(transactionId);
      try {
        await api.post(`/api/abgleich/${transactionId}/manual`, { document_ids: documentIds });
        toast.success("Gebucht");
        await inbox.mutate();
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        setBusy(null);
      }
    },
    [inbox],
  );

  const uploadStatement = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const form = new FormData();
        form.append("file", file);
        const res = await api.post<{ imported: number; duplicates: number; proposals: number }>(
          "/api/abgleich/statements",
          form,
        );
        const { imported, duplicates, proposals } = res.data;
        toast.success(
          `${imported} neue Zeile${imported === 1 ? "" : "n"}${duplicates ? `, ${duplicates} schon vorhanden` : ""} · ${proposals} Vorschlag${proposals === 1 ? "" : "e"}`,
        );
        await inbox.mutate();
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        setUploading(false);
      }
    },
    [inbox],
  );

  // j/k move, a confirms, r rejects — the same keys as the Überprüfung list.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      const key = inboxKeyFor(e);
      if (!key || items.length === 0) return;
      e.preventDefault();
      if (key === "next" || key === "prev") {
        setSelected((s) => moveSelection(s, key, items.length));
        return;
      }
      const item = items[selected];
      if (!item) return;
      void (key === "approve" ? confirm(item.transaction.id) : reject(item.transaction.id));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, selected, confirm, reject]);

  return {
    items,
    openTransactions: data.open_transactions,
    openDocuments: data.open_documents,
    summary: data.summary,
    isLoading: inbox.isLoading,
    error: inbox.error,
    retry: refresh,
    selected,
    setSelected,
    confirm,
    reject,
    ignore,
    matchManually,
    uploadStatement,
    uploading,
    busy,
  };
}
