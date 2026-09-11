import { useEffect, useState } from "react";
import useSWR from "swr";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { ClassifyInfo, Konto } from "../types";

async function fetchKontenplan(url: string): Promise<Konto[]> {
  const r = await api.get(url);
  const data = r.data?.kontenplan || r.data || {};
  return Object.entries(data).map(([k, v]) => ({ konto: k, bezeichnung: v as string }));
}

export function useKontenplan() {
  const plan = useSWR<Konto[]>("/api/kontenplan/", fetchKontenplan, { revalidateOnFocus: false });
  const info = useSWR<ClassifyInfo>("/api/classify/info", (url: string) => api.get(url).then((r) => r.data), {
    revalidateOnFocus: false,
  });

  // The table edits a local copy; the server copy is only re-read on retry.
  const [konten, setKonten] = useState<Konto[]>([]);
  useEffect(() => {
    if (plan.data) setKonten(plan.data);
  }, [plan.data]);

  const [saving, setSaving] = useState(false);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    try {
      const obj: Record<string, string> = {};
      konten.forEach((k) => { if (k.konto) obj[k.konto] = k.bezeichnung; });
      await api.put("/api/kontenplan/", { kontenplan: obj });
      toast.success("Kontenplan gespeichert");
      plan.mutate(konten, { revalidate: false });
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    setTrainResult(null);
    try {
      const res = await api.post("/api/classify/train");
      setTrainResult(`Trainiert: ${res.data.total_samples} Daten, ${((res.data.cv_accuracy || 0) * 100).toFixed(0)}% Genauigkeit`);
      info.mutate();
    } catch (e) {
      setTrainResult(`Fehler: ${errorMessage(e)}`);
    } finally {
      setTraining(false);
    }
  };

  const updateKonto = (idx: number, field: keyof Konto, value: string) =>
    setKonten((prev) => prev.map((k, i) => (i === idx ? { ...k, [field]: value } : k)));
  const addKonto = () => setKonten((prev) => [...prev, { konto: "", bezeichnung: "" }]);
  const removeKonto = (idx: number) => setKonten((prev) => prev.filter((_, j) => j !== idx));

  return {
    konten, updateKonto, addKonto, removeKonto,
    loading: plan.isLoading,
    error: plan.error,
    retry: () => plan.mutate(),
    classifyInfo: info.data ?? null,
    saving, handleSave,
    training, trainResult, handleTrain,
  };
}
