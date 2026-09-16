import { useCallback, useMemo, useState } from "react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/errors";
import { fehlendeAngaben, num, totals } from "../helpers";
import { LEERE_POSITION, LEERER_KUNDE, type FirmaProfil, type KundeForm, type PositionRow, type RechnungOut } from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useRechnungSchreiben() {
  const firma = useApi<FirmaProfil>("/api/rechnungen/firma");
  const [kunde, setKunde] = useState<KundeForm>({ ...LEERER_KUNDE });
  const [rows, setRows] = useState<PositionRow[]>([{ ...LEERE_POSITION }]);
  const [bemerkung, setBemerkung] = useState("");
  const [saving, setSaving] = useState(false);
  const [rechnung, setRechnung] = useState<RechnungOut | null>(null);

  const summe = useMemo(() => totals(rows, firma.data?.mwst_pct ?? ""), [rows, firma.data]);
  const fehlt = useMemo(() => fehlendeAngaben(kunde, rows), [kunde, rows]);

  const setKundeField = useCallback(
    (field: keyof KundeForm, value: string) => setKunde((k) => ({ ...k, [field]: value })),
    [],
  );
  const setRow = useCallback(
    (index: number, field: keyof PositionRow, value: string) =>
      setRows((current) => current.map((row, i) => (i === index ? { ...row, [field]: value } : row))),
    [],
  );
  const addRow = useCallback(() => setRows((current) => [...current, { ...LEERE_POSITION }]), []);
  const removeRow = useCallback(
    (index: number) => setRows((current) => (current.length === 1 ? current : current.filter((_, i) => i !== index))),
    [],
  );

  const speichern = useCallback(async () => {
    if (fehlt.length > 0) return;
    setSaving(true);
    try {
      const { data } = await api.post<RechnungOut>("/api/rechnungen/", {
        kunde: { ...kunde, land: "CH" },
        positionen: rows
          .filter((row) => row.bezeichnung.trim())
          .map((row) => ({
            bezeichnung: row.bezeichnung.trim(),
            menge: num(row.menge),
            einheit: row.einheit.trim(),
            einzelpreis: num(row.einzelpreis),
          })),
        bemerkung: bemerkung.trim(),
      });
      setRechnung(data);
      toast.success(`Rechnung ${data.document.invoice_no} geschrieben`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }, [bemerkung, fehlt, kunde, rows]);

  const neueRechnung = useCallback(() => {
    setRechnung(null);
    setKunde({ ...LEERER_KUNDE });
    setRows([{ ...LEERE_POSITION }]);
    setBemerkung("");
  }, []);

  /** Both views are authenticated endpoints — fetch with the token, then open the blob. */
  const oeffnen = useCallback(
    async (suffix: "html" | "pdf", mime: string) => {
      if (!rechnung) return;
      try {
        const { data } = await api.get<Blob>(`/api/rechnungen/${rechnung.document.id}/rechnung.${suffix}`, {
          responseType: "blob",
        });
        const url = URL.createObjectURL(new Blob([data], { type: mime }));
        window.open(url, "_blank", "noopener");
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } catch (e) {
        toast.error(errorMessage(e));
      }
    },
    [rechnung],
  );

  /** The browser preview. */
  const druckansicht = useCallback(() => oeffnen("html", "text/html"), [oeffnen]);
  /** The file you send a customer — Zahlteil included (B-77). */
  const pdf = useCallback(() => oeffnen("pdf", "application/pdf"), [oeffnen]);

  return {
    apiBase: API_BASE,
    firma: firma.data,
    isLoading: firma.isLoading,
    error: firma.error,
    retry: () => firma.mutate(),
    kunde,
    setKundeField,
    rows,
    setRow,
    addRow,
    removeRow,
    bemerkung,
    setBemerkung,
    summe,
    fehlt,
    saving,
    pdf,
    speichern,
    rechnung,
    neueRechnung,
    druckansicht,
  };
}
