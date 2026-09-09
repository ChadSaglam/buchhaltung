"use client";

import { Brain, Loader2, Download, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
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
  const { info, vision, loading, fetchInfo } = useModellInfo();
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

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-80 gap-3">
        <Loader2 className="w-10 h-10 animate-spin text-brand-600 dark:text-brand-300" />
        <span className="text-sm text-muted-foreground">Modell wird geladen…</span>
      </div>
    );
  }

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
              disabled={!info?.has_model && (info?.memory_count ?? 0) === 0}
              icon={<Download className="w-4 h-4" />}
            >
              Exportieren
            </Button>
            <Button
              variant="primary"
              onClick={handleTrain}
              disabled={training || (info?.total_samples ?? 0) < 5}
              loading={training}
              icon={<Sparkles className="w-4 h-4" />}
            >
              {training ? "Trainiert…" : "Modell trainieren"}
            </Button>
          </div>
        }
      />

      {/* ── System Status ─────────────────────────────────────────────── */}
      <SystemStatusBadge hasModel={info?.has_model ?? false} hasVision={vision.available} />

      {/* ── Stat Cards ────────────────────────────────────────────────── */}
      <ModelStatGrid info={info} vision={vision} acc={acc} />

      {/* ── Accuracy Bar ──────────────────────────────────────────────── */}
      {info?.has_model && <AccuracyCard info={info} acc={acc} />}

      {/* ── Inspect Tabs ──────────────────────────────────────────────── */}
      {info?.has_model && (
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
