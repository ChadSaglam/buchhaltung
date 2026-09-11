"use client";
import { useState } from "react";
import { motion } from "motion/react";
import { BookOpen, Plus, Save, Search } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { MetricCard } from "@/components/ui/metric_card";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { t } from "@/lib/i18n";
import { useKontenplan } from "./hooks/useKontenplan";
import { KontenTable } from "./components/KontenTable";
import { TrainingCard } from "./components/TrainingCard";
import type { KontenplanTab } from "./types";

const TABS: { id: KontenplanTab; label: string }[] = [
  { id: "kontenplan", label: "Kontenplan" },
  { id: "training", label: "Training" },
];

export default function KontenplanPage() {
  const [tab, setTab] = useState<KontenplanTab>("kontenplan");
  const [search, setSearch] = useState("");
  const k = useKontenplan();

  return (
    <div>
      <PageHeader icon={BookOpen} title="Kontenplan & Training" subtitle={t("kontenplan.subtitle")} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Genauigkeit" value={k.classifyInfo?.model_accuracy ? `${(k.classifyInfo.model_accuracy * 100).toFixed(0)}%` : "—"} accent="brand" />
        <MetricCard title="Konten" value={k.konten.length} accent="success" />
        <MetricCard title="Gedächtnis" value={k.classifyInfo?.memory_count || 0} accent="warning" />
        <MetricCard title="Korrekturen" value={k.classifyInfo?.correction_count || 0} accent="neutral" />
      </div>

      <div role="tablist" aria-label="Kontenplan-Bereiche" className="flex border-b border-border mb-6">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === item.id
                ? "border-brand-600 text-brand-600 dark:text-brand-300 dark:border-brand-300"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "kontenplan" && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
          {k.loading ? (
            <PageSkeleton rows={8} />
          ) : k.error ? (
            <ErrorState error={k.error} onRetry={k.retry} />
          ) : (
            <>
              <div className="flex gap-3 mb-4">
                <div className="relative w-64">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <input
                    type="search"
                    aria-label={t("common.search")}
                    placeholder={t("common.search")}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 border border-input rounded-lg text-sm bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-ring transition-all"
                  />
                </div>
                <div className="flex-1" />
                <Button variant="outline" size="sm" icon={<Plus className="h-4 w-4" aria-hidden="true" />} onClick={k.addKonto}>
                  {t("kontenplan.add")}
                </Button>
              </div>
              <KontenTable konten={k.konten} search={search} onUpdate={k.updateKonto} onRemove={k.removeKonto} onAdd={k.addKonto} />
              <div className="mt-4 flex gap-3">
                <Button variant="primary" onClick={k.handleSave} disabled={k.saving} loading={k.saving} icon={<Save className="h-4 w-4" aria-hidden="true" />}>
                  {k.saving ? "Speichert..." : t("kontenplan.save")}
                </Button>
              </div>
            </>
          )}
        </motion.div>
      )}

      {tab === "training" && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
          <TrainingCard
            correctionCount={k.classifyInfo?.correction_count ?? 0}
            training={k.training}
            trainResult={k.trainResult}
            onTrain={k.handleTrain}
          />
        </motion.div>
      )}
    </div>
  );
}
