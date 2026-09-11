import { MetricCardSkeleton, Skeleton } from "@/components/shared/LoadingSkeleton";
import { t } from "@/lib/i18n";

interface Props {
  /** Title + subtitle placeholder (omit when the page renders its own header). */
  header?: boolean;
  /** Number of metric-card placeholders in the top grid (0 = none). */
  metrics?: number;
  /** Number of table-row placeholders (0 = none). */
  rows?: number;
  className?: string;
}

/**
 * The skeleton every dashboard page shows while its first request is in
 * flight. Announced once to assistive tech via `aria-busy` + a visually
 * hidden label; the shapes mirror the page (header → metrics → table).
 */
export function PageSkeleton({ header = false, metrics = 0, rows = 6, className = "" }: Props) {
  return (
    <div className={`space-y-6 ${className}`} aria-busy="true" aria-live="polite" data-testid="page-skeleton">
      <span className="sr-only">{t("common.loading")}</span>
      {header && (
        <div className="space-y-2">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </div>
      )}
      {metrics > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: metrics }).map((_, i) => (
            <MetricCardSkeleton key={i} />
          ))}
        </div>
      )}
      {rows > 0 && (
        <div className="rounded-xl border border-border bg-card p-5">
          <Skeleton className="mb-4 h-4 w-40" />
          <div className="space-y-3">
            {Array.from({ length: rows }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
