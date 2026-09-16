"use client";
import { useCallback, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { versandBody, type VersandEntwurf, type VersandErgebnis } from "../versand";

/**
 * Open the preview, then send (B-79). Shared by the "invoice written" card and
 * the Rechnungen list, because both want the same dialog.
 */
export function useVersand(onSent?: () => void | Promise<unknown>) {
  const [draft, setDraft] = useState<VersandEntwurf | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [sending, setSending] = useState(false);

  const oeffnen = useCallback(async (documentId: number) => {
    setLoadingId(documentId);
    try {
      const { data } = await api.get<VersandEntwurf>(`/api/rechnungen/${documentId}/versand`);
      setDraft(data);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setLoadingId(null);
    }
  }, []);

  const schliessen = useCallback(() => setDraft(null), []);

  const senden = useCallback(
    async (edited: { empfaenger: string; subject: string; text: string }) => {
      if (!draft) return;
      setSending(true);
      try {
        const { data } = await api.post<VersandErgebnis>(
          `/api/rechnungen/${draft.document_id}/versand`,
          versandBody(draft, edited),
        );
        toast.success(`Rechnung an ${data.empfaenger} gesendet`);
        setDraft(null);
        await onSent?.();
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        setSending(false);
      }
    },
    [draft, onSent],
  );

  return { draft, loadingId, sending, oeffnen, schliessen, senden };
}
