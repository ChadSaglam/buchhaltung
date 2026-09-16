"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useApi } from "@/hooks/useApi";
import api from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import {
  aktive,
  betragWert,
  monatsende,
  type AbrechnungListItem,
  type Lohnlauf,
  type LohnSettings,
  type Mitarbeiter,
} from "@/lib/lohn";

export interface AbrechnungListe {
  eintraege: AbrechnungListItem[];
  brutto_total: number;
  netto_total: number;
  ag_total: number;
}

const heute = () => new Date();

/**
 * Payroll's page state (B-72).
 *
 * The preview is fetched on demand rather than as the employee/month change,
 * because a preview is a POST that the backend refuses while a rate is missing,
 * and firing it on every keystroke would fill the screen with errors the user
 * has not caused yet.
 */
export function useLohn() {
  const settings = useApi<LohnSettings>("/api/lohn/settings");
  const mitarbeiter = useApi<Mitarbeiter[]>("/api/lohn/mitarbeiter");

  const [jahr, setJahr] = useState(() => heute().getFullYear());
  const [monat, setMonat] = useState(() => heute().getMonth() + 1);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const [zulagen, setZulagen] = useState("");
  const [dreizehnter, setDreizehnter] = useState(false);

  const [lauf, setLauf] = useState<Lohnlauf | null>(null);
  const [laufFehler, setLaufFehler] = useState("");
  const [busy, setBusy] = useState(false);

  const abrechnungen = useApi<AbrechnungListe>(`/api/lohn/abrechnungen?jahr=${jahr}`);

  const liste = useMemo(() => mitarbeiter.data ?? [], [mitarbeiter.data]);
  const waehlbar = useMemo(() => aktive(liste, monatsende(jahr, monat)), [liste, jahr, monat]);

  // Keep the selection valid: an employee who left before the chosen month is
  // no longer in the list, and a stale id would post a payslip for the wrong person.
  useEffect(() => {
    if (gewaehlt != null && waehlbar.some((m) => m.id === gewaehlt)) return;
    setGewaehlt(waehlbar[0]?.id ?? null);
    setLauf(null);
  }, [waehlbar, gewaehlt]);

  const bereit = (settings.data?.fehlt ?? []).length === 0;
  const person = useMemo(() => waehlbar.find((m) => m.id === gewaehlt), [waehlbar, gewaehlt]);

  const body = useCallback(
    () => ({
      mitarbeiter_id: gewaehlt,
      jahr,
      monat,
      zulagen: betragWert(zulagen) ?? 0,
      dreizehnter,
    }),
    [gewaehlt, jahr, monat, zulagen, dreizehnter],
  );

  const vorschau = useCallback(async () => {
    if (gewaehlt == null) return;
    setBusy(true);
    setLaufFehler("");
    try {
      const { data } = await api.post<Lohnlauf>("/api/lohn/vorschau", body());
      setLauf(data);
    } catch (e) {
      setLauf(null);
      setLaufFehler(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [gewaehlt, body]);

  const abrechnen = useCallback(async () => {
    if (gewaehlt == null) return;
    setBusy(true);
    setLaufFehler("");
    try {
      const { data } = await api.post<{ abrechnung: Lohnlauf }>("/api/lohn/abrechnen", body());
      setLauf(data.abrechnung);
      await abrechnungen.mutate();
      toast.success("Lohn abgerechnet und verbucht");
    } catch (e) {
      setLaufFehler(errorMessage(e));
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [gewaehlt, body, abrechnungen]);

  const saetzeSpeichern = useCallback(
    async (werte: Record<string, number | null>) => {
      try {
        const { data } = await api.put<LohnSettings>("/api/lohn/settings", werte);
        await settings.mutate(data, { revalidate: false });
        toast.success("Sätze gespeichert");
      } catch (e) {
        toast.error(errorMessage(e));
      }
    },
    [settings],
  );

  const mitarbeiterAnlegen = useCallback(
    async (werte: Record<string, unknown>) => {
      try {
        await api.post("/api/lohn/mitarbeiter", werte);
        await mitarbeiter.mutate();
        toast.success("Mitarbeiter angelegt");
        return true;
      } catch (e) {
        toast.error(errorMessage(e));
        return false;
      }
    },
    [mitarbeiter],
  );

  const mitarbeiterAendern = useCallback(
    async (id: number, werte: Record<string, unknown>) => {
      try {
        await api.put(`/api/lohn/mitarbeiter/${id}`, werte);
        await mitarbeiter.mutate();
        toast.success("Gespeichert");
        return true;
      } catch (e) {
        toast.error(errorMessage(e));
        return false;
      }
    },
    [mitarbeiter],
  );

  return {
    settings: settings.data,
    bereit,
    isLoading: settings.isLoading || mitarbeiter.isLoading,
    error: settings.error ?? mitarbeiter.error,
    retry: () => {
      settings.mutate();
      mitarbeiter.mutate();
    },
    mitarbeiter: liste,
    waehlbar,
    person,
    gewaehlt,
    setGewaehlt: (id: number | null) => {
      setGewaehlt(id);
      setLauf(null);
    },
    jahr,
    monat,
    setJahr: (value: number) => {
      setJahr(value);
      setLauf(null);
    },
    setMonat: (value: number) => {
      setMonat(value);
      setLauf(null);
    },
    zulagen,
    setZulagen: (value: string) => {
      setZulagen(value);
      setLauf(null);
    },
    dreizehnter,
    setDreizehnter: (value: boolean) => {
      setDreizehnter(value);
      setLauf(null);
    },
    lauf,
    laufFehler,
    busy,
    vorschau,
    abrechnen,
    abrechnungen: abrechnungen.data,
    saetzeSpeichern,
    mitarbeiterAnlegen,
    mitarbeiterAendern,
  };
}
