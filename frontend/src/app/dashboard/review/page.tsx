"use client";

import { useState } from "react";
import useSWR from "swr";
import { motion } from "motion/react";
import toast from "react-hot-toast";
import { CheckCircle2, XCircle, ListChecks, ScanLine } from "lucide-react";
import { getReviewQueue, approveReviewItem, rejectReviewItem } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { t } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/page_header";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";

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

interface ReviewQueue {
  items: ReviewItem[];
  threshold?: number;
}

export default function ReviewPage() {
  const { data, error, isLoading, mutate } = useSWR<ReviewQueue>("/api/review/", getReviewQueue, {
    revalidateOnFocus: false,
  });
  const [busyId, setBusyId] = useState<number | null>(null);
  const items = data?.items ?? [];
  const threshold = typeof data?.threshold === "number" ? data.threshold : 0.8;

  const decide = async (id: number, action: typeof approveReviewItem | typeof rejectReviewItem) => {
    setBusyId(id);
    try {
      await action(id);
      await mutate(
        (prev) => (prev ? { ...prev, items: prev.items.filter((i) => i.id !== id) } : prev),
        { revalidate: false }
      );
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusyId(null);
    }
  };
  const handleApprove = (id: number) => decide(id, approveReviewItem);
  const handleReject = (id: number) => decide(id, rejectReviewItem);

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

      {isLoading ? (
        <PageSkeleton rows={4} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => mutate()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title={t("review.empty")}
          description={t("empty.review.desc")}
          action={
            <ButtonLink variant="outline" href="/dashboard/scanner" icon={<ScanLine className="h-4 w-4" aria-hidden="true" />}>
              {t("empty.review.action")}
            </ButtonLink>
          }
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
