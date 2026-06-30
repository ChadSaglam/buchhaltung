"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import { CheckCircle2, XCircle, Loader2, ListChecks } from "lucide-react";
import { getReviewQueue, approveReviewItem, rejectReviewItem } from "@/lib/api";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/shared/EmptyState";

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
    <div className="space-y-6">
      <PageHeader
        icon={ListChecks}
        title="Überprüfungs-Warteschlange"
        subtitle={`Buchungen mit Konfidenz unter ${Math.round(threshold * 100)}% prüfen und bestätigen`}
        action={
          <Badge tone={items.length > 0 ? "warning" : "success"} dot>
            {items.length} offen
          </Badge>
        }
      />

      {loading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" /> Laden...
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title="Keine Einträge zur Überprüfung"
          description="Alle Buchungen haben eine ausreichende Konfidenz."
        />
      ) : (
        <div className="space-y-3">
          {items.map((item, idx) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, delay: Math.min(idx * 0.05, 0.3) }}
              className="flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border border-border bg-card p-4"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{item.beschreibung}</p>
                <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="tabular-nums">Betrag: {item.betrag.toFixed(2)}</span>
                  <span className="font-mono">
                    {item.predicted_soll} / {item.predicted_haben}
                    {item.predicted_mwst_code ? ` · ${item.predicted_mwst_code}` : ""}
                  </span>
                  <span>Quelle: {item.source}</span>
                </div>
              </div>

              <Badge
                tone={item.confidence < 0.5 ? "danger" : "warning"}
              >
                {Math.round(item.confidence * 100)}%
              </Badge>

              <div className="flex shrink-0 gap-2">
                <Button
                  variant="success"
                  size="sm"
                  onClick={() => handleApprove(item.id)}
                  disabled={busyId === item.id}
                  loading={busyId === item.id}
                  icon={<CheckCircle2 className="h-4 w-4" />}
                >
                  Bestätigen
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleReject(item.id)}
                  disabled={busyId === item.id}
                  icon={<XCircle className="h-4 w-4" />}
                >
                  Verwerfen
                </Button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
