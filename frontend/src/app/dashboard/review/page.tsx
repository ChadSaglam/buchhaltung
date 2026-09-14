"use client";

import { ListChecks, ScanLine } from "lucide-react";
import { t } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/page_header";
import { ButtonLink } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { useReviewQueue } from "./hooks/useReviewQueue";
import { ReviewList } from "./components/ReviewList";

export default function ReviewPage() {
  const q = useReviewQueue();

  return (
    <div className="space-y-6">
      <PageHeader
        icon={ListChecks}
        title="Überprüfungs-Warteschlange"
        subtitle={`Buchungen mit Konfidenz unter ${Math.round(q.threshold * 100)}% prüfen und bestätigen`}
        action={
          <Badge tone={q.items.length > 0 ? "warning" : "success"} dot>
            {q.items.length} offen
          </Badge>
        }
      />

      {q.isLoading ? (
        <PageSkeleton rows={4} />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={q.retry} />
      ) : q.items.length === 0 ? (
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
        <ReviewList items={q.items} selected={q.selected} onSelect={q.setSelected} onApprove={q.approve} onReject={q.reject} />
      )}
    </div>
  );
}
