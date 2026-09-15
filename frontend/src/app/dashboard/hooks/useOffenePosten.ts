import { useCallback, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import type { MahnungDraft, OffenePostenResponse, OpenItemOut } from "@/lib/offene-posten";

/** Offene Posten for the Heute surface: both sides plus the Mahnung draft flow. */
export function useOffenePosten() {
  const posten = useApi<OffenePostenResponse>("/api/offene-posten/");
  const [draft, setDraft] = useState<MahnungDraft | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [recording, setRecording] = useState(false);

  /** Preview first — nothing is stored until the owner says it went out. */
  const openDraft = useCallback(async (item: OpenItemOut) => {
    setLoadingId(item.document.id);
    try {
      const res = await api.get<MahnungDraft>(`/api/offene-posten/${item.document.id}/mahnung`);
      setDraft(res.data);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setLoadingId(null);
    }
  }, []);

  const closeDraft = useCallback(() => setDraft(null), []);

  const recordSent = useCallback(async () => {
    if (!draft) return;
    setRecording(true);
    try {
      const res = await api.post<MahnungDraft>(`/api/offene-posten/${draft.document_id}/mahnung`, {
        stufe: draft.stufe,
      });
      toast.success(`${res.data.stufe_label} erfasst`);
      setDraft(null);
      await posten.mutate();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setRecording(false);
    }
  }, [draft, posten]);

  /** The letter needs the bearer token, so it is fetched and opened as a blob. */
  const openLetter = useCallback(async (item: MahnungDraft) => {
    try {
      const res = await api.get(`/api/offene-posten/${item.document_id}/mahnung.html?stufe=${item.stufe}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: "text/html" }));
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, []);

  return {
    debitoren: posten.data?.debitoren,
    kreditoren: posten.data?.kreditoren,
    isLoading: posten.isLoading,
    error: posten.error,
    retry: () => posten.mutate(),
    draft,
    openDraft,
    closeDraft,
    loadingId,
    recording,
    recordSent,
    openLetter,
  };
}
