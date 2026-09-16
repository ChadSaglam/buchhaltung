import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import type { EmailEingang, MailSettings } from "../types";

export function useEmailEingang() {
  const eingang = useApi<EmailEingang>("/api/email/");
  const [allowList, setAllowList] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (eingang.data) setAllowList(eingang.data.einstellungen.allow_list ?? "");
  }, [eingang.data]);

  const apply = useCallback(
    async (einstellungen: MailSettings) => {
      if (!eingang.data) return;
      await eingang.mutate({ ...eingang.data, einstellungen }, { revalidate: false });
    },
    [eingang],
  );

  const speichern = useCallback(async () => {
    setSaving(true);
    try {
      const { data } = await api.put<MailSettings>("/api/email/einstellungen", { allow_list: allowList });
      await apply(data);
      setSaved(true);
      toast.success("Absenderliste gespeichert");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }, [allowList, apply]);

  const umschalten = useCallback(async () => {
    const aktiv = !(eingang.data?.einstellungen.aktiv ?? true);
    try {
      const { data } = await api.put<MailSettings>("/api/email/einstellungen", { aktiv });
      await apply(data);
      toast.success(aktiv ? "E-Mail-Eingang eingeschaltet" : "E-Mail-Eingang ausgeschaltet");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, [apply, eingang.data]);

  const absenderErlauben = useCallback(
    async (adresse: string) => {
      try {
        const { data } = await api.post<MailSettings>("/api/email/absender", { adresse });
        setAllowList(data.allow_list ?? "");
        await apply(data);
        toast.success(`${adresse} darf jetzt Belege schicken`);
      } catch (e) {
        toast.error(errorMessage(e));
      }
    },
    [apply],
  );

  const jetztAbrufen = useCallback(async () => {
    setFetching(true);
    try {
      const { data } = await api.post<{ geholt: number; hinweis: string }>("/api/email/abrufen");
      await eingang.mutate();
      toast.success(data.geholt ? `${data.geholt} Nachricht(en) geholt` : "Keine neuen Nachrichten");
      if (data.hinweis) toast(data.hinweis);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setFetching(false);
    }
  }, [eingang]);

  return {
    data: eingang.data,
    isLoading: eingang.isLoading,
    error: eingang.error,
    retry: () => eingang.mutate(),
    allowList,
    setAllowList: (value: string) => {
      setSaved(false);
      setAllowList(value);
    },
    saving,
    saved,
    speichern,
    umschalten,
    absenderErlauben,
    fetching,
    jetztAbrufen,
  };
}
