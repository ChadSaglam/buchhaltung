"use client";

import { useState } from "react";
import { Brain, Plus, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import type { BuchungRow, MWST_CODE_OPTIONS, MWST_PCT_OPTIONS } from "../types";
import { calcMwst } from "../helpers";

interface ManualEntryProps {
  onAddRow: (row: BuchungRow) => void;
  nextNr: number;
}

export function ManualEntry({ onAddRow, nextNr }: ManualEntryProps) {
  const [beschreibung, setBeschreibung] = useState("");
  const [betrag, setBetrag] = useState("");
  const [classifying, setClassifying] = useState(false);
  const [result, setResult] = useState<{
    kt_soll: string; kt_haben: string; mwst_code: string; mwst_pct: string; confidence: number; source: string;
  } | null>(null);

  const handleClassify = async () => {
    if (!beschreibung.trim()) return;
    setClassifying(true);
    try {
      const res = await api.post("/api/classify/predict", {
        beschreibung: beschreibung.trim(),
        betrag: parseFloat(betrag) || 0,
      });
      setResult(res.data);
    } catch {
      toast.error("Klassifizierung fehlgeschlagen");
    } finally {
      setClassifying(false);
    }
  };

  const handleAdd = () => {
    if (!result || !betrag) return;
    const amt = parseFloat(betrag);
    onAddRow({
      nr: nextNr,
      datum: new Date().toISOString().slice(0, 10),
      beleg: "",
      rechnung: "",
      beschreibung: beschreibung.trim(),
      kt_soll: result.kt_soll,
      kt_haben: result.kt_haben,
      betrag: amt,
      mwstcode: result.mwst_code,
      artbetrag: result.mwst_code ? "1" : "",
      mwstpct: result.mwst_pct,
      mwstchf: calcMwst(amt, result.mwst_pct),
      ks3: "",
    });
    setBeschreibung("");
    setBetrag("");
    setResult(null);
    toast.success("Buchung hinzugefügt");
  };

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Brain className="h-5 w-5 text-brand-600" />
        <p className="text-sm font-semibold text-foreground">Manuelle Klassifizierung</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-[1fr_120px_auto] gap-3">
        <input
          value={beschreibung}
          onChange={(e) => { setBeschreibung(e.target.value); setResult(null); }}
          placeholder="Beschreibung eingeben..."
          className="rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          onKeyDown={(e) => e.key === "Enter" && handleClassify()}
        />
        <input
          type="number"
          step="0.01"
          value={betrag}
          onChange={(e) => setBetrag(e.target.value)}
          placeholder="Betrag"
          className="rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          onClick={handleClassify}
          disabled={classifying || !beschreibung.trim()}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          {classifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
          Klassifizieren
        </button>
      </div>

      {result && (
        <div className="flex items-center justify-between rounded-lg bg-accent/50 px-4 py-3">
          <div className="flex items-center gap-4 text-sm">
            <span className="font-mono"><strong>Soll:</strong> {result.kt_soll}</span>
            <span className="font-mono"><strong>Haben:</strong> {result.kt_haben}</span>
            <span><strong>MwSt:</strong> {result.mwst_code} {result.mwst_pct}%</span>
            <span className="text-muted-foreground">({(result.confidence * 100).toFixed(0)}% · {result.source})</span>
          </div>
          <button
            onClick={handleAdd}
            disabled={!betrag}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Hinzufügen
          </button>
        </div>
      )}
    </div>
  );
}
