"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import { CheckCircle2, XCircle, Loader2, Inbox } from "lucide-react";
import { getReviewQueue, approveReviewItem, rejectReviewItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ReviewItem {
  id: number;
  beschreibung: string;
  betrag: number;
  predicted_soll: string;
  predicted_haben: string;
  predicted_mwst_code: string;
  predicted_mwst_pct: string;
  confidence: number;
  source: string;
  status: string;
  created_at: string | null;
}

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [threshold, setThreshold] = useState<number>(0.8);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getReviewQueue();
      setItems(data.items ?? []);
      if (typeof data.threshold === "number") setThreshold(data.threshold);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleApprove = async (id: number) => {
    setBusyId(id);
    try {
      await approveReviewItem(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (id: number) => {
    setBusyId(id);
    try {
      await rejectReviewItem(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Überprüfungs-Warteschlange</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Buchungen mit Konfidenz unter {Math.round(threshold * 100)}% prüfen und bestätigen
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700">
          {items.length} offen
        </span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" /> Laden...
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Inbox className="h-10 w-10 mb-3 opacity-50" />
          <p className="text-sm">Keine Einträge zur Überprüfung</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border border-border bg-card p-4"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{item.beschreibung}</p>
                <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>Betrag: {item.betrag.toFixed(2)}</span>
                  <span className="font-mono">
                    {item.predicted_soll} / {item.predicted_haben}
                    {item.predicted_mwst_code ? ` · ${item.predicted_mwst_code}` : ""}
                  </span>
                  <span>Quelle: {item.source}</span>
                </div>
              </div>

              <span
                className={cn(
                  "shrink-0 rounded-full px-2.5 py-1 text-xs font-medium",
                  item.confidence < 0.5
                    ? "bg-red-50 text-red-700"
                    : "bg-amber-50 text-amber-700"
                )}
              >
                {Math.round(item.confidence * 100)}%
              </span>

              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() => handleApprove(item.id)}
                  disabled={busyId === item.id}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  {busyId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  Bestätigen
                </button>
                <button
                  onClick={() => handleReject(item.id)}
                  disabled={busyId === item.id}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
                >
                  <XCircle className="h-4 w-4" />
                  Verwerfen
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}