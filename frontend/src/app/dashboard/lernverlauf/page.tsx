"use client";
import { useState } from "react";
import { GraduationCap, Search } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { MetricCard } from "@/components/ui/metric_card";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { t } from "@/lib/i18n";
import { useLernverlauf } from "./hooks/useLernverlauf";
import { Charts } from "./components/Charts";
import { MemoryTable, CorrectionsTable } from "./components/Tables";
import type { LernverlaufTab } from "./types";

const TABS: { id: LernverlaufTab; label: string }[] = [
  { id: "charts", label: "lernverlauf.charts_tab" },
  { id: "memory", label: "lernverlauf.memory_tab" },
  { id: "corrections", label: "lernverlauf.corrections_tab" },
];

export default function LernverlaufPage() {
  const [tab, setTab] = useState<LernverlaufTab>("charts");
  const [search, setSearch] = useState("");
  const { data, error, loading, retry } = useLernverlauf();

  const header = <PageHeader icon={GraduationCap} title={t("lernverlauf.title")} subtitle={t("lernverlauf.subtitle")} />;

  if (loading) {
    return (
      <div>
        {header}
        <PageSkeleton metrics={4} rows={6} />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div>
        {header}
        <ErrorState error={error} onRetry={retry} />
      </div>
    );
  }

  return (
    <div>
      {header}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title={t("dashboard.memory")} value={data.info.memory_count || 0} accent="brand" />
        <MetricCard title={t("common.corrections")} value={data.info.correction_count || 0} accent="warning" />
        <MetricCard title={t("dashboard.bookings")} value={data.stats.booking_count || 0} accent="success" />
        <MetricCard title="Konten gelernt" value={data.stats.memory_distribution?.length || 0} accent="neutral" />
      </div>

      <div className="flex items-center border-b border-border mb-6 gap-4">
        <div role="tablist" aria-label={t("lernverlauf.title")} className="flex">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === item.id
                  ? "border-brand-600 text-brand-600 dark:text-brand-300 dark:border-brand-300"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t(item.label)}
            </button>
          ))}
        </div>
        {tab !== "charts" && (
          <div className="ml-auto relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            <input
              type="search"
              aria-label={t("common.search")}
              placeholder={t("common.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 border border-input rounded-lg text-sm w-56 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-ring transition-all"
            />
          </div>
        )}
      </div>

      {tab === "charts" && <Charts stats={data.stats} />}
      {tab === "memory" && <MemoryTable entries={data.memory} search={search} />}
      {tab === "corrections" && <CorrectionsTable entries={data.corrections} search={search} />}
    </div>
  );
}
