import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import type { FirmaProfil } from "../../neu/types";

export type FirmaFeld =
  | "name" | "strasse" | "hausnummer" | "plz" | "ort"
  | "iban" | "mwst_nr" | "email" | "telefon"
  | "konto_debitoren" | "konto_ertrag" | "konto_bank" | "mwst_code" | "mwst_pct";

const FELDER: FirmaFeld[] = [
  "name", "strasse", "hausnummer", "plz", "ort",
  "iban", "mwst_nr", "email", "telefon",
  "konto_debitoren", "konto_ertrag", "konto_bank", "mwst_code", "mwst_pct",
];

type Entwurf = Record<FirmaFeld, string> & { zahlungsfrist_tage: string };

const LEER = {
  ...(Object.fromEntries(FELDER.map((f) => [f, ""])) as Record<FirmaFeld, string>),
  zahlungsfrist_tage: "30",
};

export function useFirma() {
  const firma = useApi<FirmaProfil>("/api/rechnungen/firma");
  const [entwurf, setEntwurf] = useState<Entwurf>(LEER);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!firma.data) return;
    const data = firma.data as unknown as Record<string, unknown>;
    setEntwurf({
      ...(Object.fromEntries(FELDER.map((f) => [f, String(data[f] ?? "")])) as Record<FirmaFeld, string>),
      zahlungsfrist_tage: String(data.zahlungsfrist_tage ?? 30),
    });
  }, [firma.data]);

  const setFeld = useCallback((field: FirmaFeld | "zahlungsfrist_tage", value: string) => {
    setSaved(false);
    setEntwurf((current) => ({ ...current, [field]: value }));
  }, []);

  const speichern = useCallback(async () => {
    setSaving(true);
    try {
      const body: Record<string, unknown> = Object.fromEntries(FELDER.map((f) => [f, entwurf[f]]));
      const frist = Number.parseInt(entwurf.zahlungsfrist_tage, 10);
      body.zahlungsfrist_tage = Number.isFinite(frist) ? Math.max(0, Math.min(365, frist)) : 30;
      const { data } = await api.put<FirmaProfil>("/api/rechnungen/firma", body);
      await firma.mutate(data, { revalidate: false });
      setSaved(true);
      toast.success("Firmenprofil gespeichert");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }, [entwurf, firma]);

  return {
    profil: firma.data,
    entwurf,
    setFeld,
    isLoading: firma.isLoading,
    error: firma.error,
    retry: () => firma.mutate(),
    saving,
    saved,
    speichern,
  };
}
