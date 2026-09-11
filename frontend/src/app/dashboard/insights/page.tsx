"use client";

import { Sparkles, RefreshCw, FileText } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button, ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { t } from "@/lib/i18n";
import { useInsights } from "./hooks/useInsights";
import { useAiSummary } from "./hooks/useAiSummary";
import { SearchCard } from "./components/SearchCard";
import { ResultsTable } from "./components/ResultsTable";
import { SummaryCard } from "./components/SummaryCard";
import { MonthlyBreakdown } from "./components/MonthlyBreakdown";
import { AnomaliesCard } from "./components/AnomaliesCard";

export default function InsightsPage() {
  const { bookings, loading, error, load, query, setQuery, results, months, anomalies, activeFilters } = useInsights();
  const ai = useAiSummary();

  const latest = months[0];
  const empty = !loading && !error && bookings.length === 0;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Sparkles}
        title="Insights & Suche"
        subtitle="Buchungen in natürlicher Sprache durchsuchen, Monatsauswertung und Auffälligkeiten"
        action={
          <Button variant="ghost" size="sm" icon={<RefreshCw className="h-4 w-4" />} onClick={load} disabled={loading}>
            {t("state.reload")}
          </Button>
        }
      />

      {error ? <ErrorState error={error} onRetry={load} /> : null}
      {loading && <PageSkeleton rows={5} />}
      {empty && (
        <EmptyState
          icon={Sparkles}
          title={t("empty.insights.title")}
          description={t("empty.insights.desc")}
          action={
            <ButtonLink href="/dashboard/kontoauszug" icon={<FileText className="h-4 w-4" aria-hidden="true" />}>
              {t("empty.insights.action")}
            </ButtonLink>
          }
        />
      )}

      {/* Natural-language search */}
      {!loading && !error && !empty && (
        <SearchCard query={query} setQuery={setQuery} activeFilters={activeFilters} resultCount={results.length} />
      )}

      {/* Search results */}
      {!empty && query && <ResultsTable results={results} loading={loading} />}

      {/* Monthly summary + anomalies (hidden while actively searching) */}
      {!loading && !error && !empty && !query && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            <SummaryCard latest={latest} hasBookings={bookings.length > 0} ai={ai} />
            <MonthlyBreakdown months={months} />
          </div>
          <div className="self-start">
            <AnomaliesCard anomalies={anomalies} loading={loading} />
          </div>
        </div>
      )}
    </div>
  );
}
