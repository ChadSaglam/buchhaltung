"use client";

import { Brain, Download, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { t } from "@/lib/i18n";
import { useModellInfo } from "./hooks/useModellInfo";
import { useModellActions } from "./hooks/useModellActions";
import { useModellInspect } from "./hooks/useModellInspect";
import { SystemStatusBadge } from "./components/SystemStatusBadge";
import { ModelStatGrid } from "./components/ModelStatGrid";
import { AccuracyCard } from "./components/AccuracyCard";
import { InspectTabs } from "./components/InspectTabs";
import { BananaImportCard } from "./components/BananaImportCard";
import { ExportCard, RestoreCard } from "./components/ExportRestoreCards";
import { PipelineCard } from "./components/PipelineCard";
import { DangerZone } from "./components/DangerZone";

export default function ModellPage() {
  const { info, vision, loading, error, fetchInfo } = useModellInfo();
  const {
    training,
    handleTrain,
    dangerConfirm,
    setDangerConfirm,
    handleDangerAction,
    handleDownload,
    handleUploadBundle,
  } = useModellActions(fetchInfo);
  const inspect = useModellInspect();

  const acc = info?.model_accuracy ?? 0;

  if (loading) return <PageSkeleton header metrics={4} rows={4} className="max-w-5xl mx-auto" />;
  if (error || !info) return <ErrorState error={error} onRetry={fetchInfo} />;
  const canTrain = (info.total_samples ?? 0) >= 5;

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <PageHeader
        icon={Brain}
        title="Modell Manager"
        subtitle="Buchhaltung ML-Modell verwalten, trainieren & inspizieren"
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => handleDownload("bundle")}
              disabled={!info.has_model && (info.memory_count ?? 0) === 0}
              icon={<Download className="w-4 h-4" />}
            >
              Exportieren
            </Button>
            <Button
              variant="primary"
              onClick={handleTrain}
              disabled={training || !canTrain}
              loading={training}
              icon={<Sparkles className="w-4 h-4" />}
            >
              {training ? "Trainiert…" : "Modell trainieren"}
            </Button>
          </div>
        }
      />

      {/* ── System Status ─────────────────────────────────────────────── */}
      <SystemStatusBadge hasModel={info.has_model} hasVision={vision.available} />

      {/* ── Stat Cards ────────────────────────────────────────────────── */}
      <ModelStatGrid info={info} vision={vision} acc={acc} />

      {/* ── Accuracy Bar ──────────────────────────────────────────────── */}
      {info.has_model ? (
        <AccuracyCard info={info} acc={acc} />
      ) : (
        <EmptyState
          icon={Brain}
          title={t("empty.modell.title")}
          description={t("empty.modell.desc")}
          action={
            <Button onClick={handleTrain} disabled={training || !canTrain} loading={training} icon={<Sparkles className="w-4 h-4" aria-hidden="true" />}>
              {t("empty.modell.action")}
            </Button>
          }
        />
      )}

      {/* ── Inspect Tabs ──────────────────────────────────────────────── */}
      {info.has_model && (
        <InspectTabs info={info} training={training} handleTrain={handleTrain} inspect={inspect} />
      )}

      {/* ── Import Section ────────────────────────────────────────────── */}
      <BananaImportCard fetchInfo={fetchInfo} />

      {/* ── Download & Upload ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ExportCard info={info} handleDownload={handleDownload} />
        <RestoreCard handleUploadBundle={handleUploadBundle} />
      </div>

      {/* ── Pipeline ──────────────────────────────────────────────────── */}
      <PipelineCard />

      {/* ── Danger Zone ───────────────────────────────────────────────── */}
      <DangerZone
        info={info}
        dangerConfirm={dangerConfirm}
        setDangerConfirm={setDangerConfirm}
        handleDangerAction={handleDangerAction}
      />
    </div>
  );
}
