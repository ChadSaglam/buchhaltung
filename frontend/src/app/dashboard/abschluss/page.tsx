"use client";

import { AlertTriangle, PackageCheck, ShieldCheck, Upload } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { MetricCard } from "@/components/ui/metric_card";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { formatCHF } from "@/lib/format";
import { useAbschluss } from "./hooks/useAbschluss";
import { exportLabel, formatPeriod } from "./helpers";
import { ExportChecklist } from "./components/ExportChecklist";
import { MonthCheck } from "./components/MonthCheck";
import { BatchList } from "./components/BatchList";

export default function AbschlussPage() {
  const a = useAbschluss();
  const { preflight } = a;
  const canExport = preflight.ready && !a.exporting;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={PackageCheck}
        title="Abschluss"
        subtitle="Alles abgeglichen? Dann geht es als ein Stapel nach Banana — jede Buchung genau einmal"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard
          title="Bereit zum Export"
          value={preflight.exportable}
          subtitle={preflight.exportable ? formatCHF(preflight.total) : "alles schon übergeben"}
          icon={<Upload className="h-5 w-5" />}
          accent={preflight.exportable ? "brand" : "neutral"}
        />
        <MetricCard
          title="Zeitraum"
          value={formatPeriod(preflight.period_from, preflight.period_to)}
          subtitle="Datum der ersten und letzten Buchung"
          icon={<PackageCheck className="h-5 w-5" />}
          accent="info"
        />
        <MetricCard
          title="Zu korrigieren"
          value={preflight.blockers}
          subtitle={preflight.blockers ? "blockiert den Export" : "keine Fehler gefunden"}
          icon={preflight.blockers ? <AlertTriangle className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
          accent={preflight.blockers ? "danger" : "success"}
        />
      </div>

      {a.isLoading ? (
        <PageSkeleton rows={4} />
      ) : a.error ? (
        <ErrorState error={a.error} onRetry={a.retry} />
      ) : (
        <>
          <section aria-label="Monatsabschluss" className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Monat prüfen</h2>
            <MonthCheck />
          </section>

          <section aria-label="Prüfliste" className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Vor dem Export</h2>
            <ExportChecklist checks={preflight.checks} />

            <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{exportLabel(preflight.exportable, preflight.ready)}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Die Buchungen werden als exportiert markiert und im nächsten Stapel nicht wiederholt.
                </p>
              </div>
              {a.confirming ? (
                <div className="flex shrink-0 gap-2">
                  <Button variant="primary" loading={a.exporting} onClick={a.runExport}>
                    Ja, exportieren
                  </Button>
                  <Button variant="ghost" disabled={a.exporting} onClick={() => a.setConfirming(false)}>
                    Abbrechen
                  </Button>
                </div>
              ) : (
                <Button
                  className="shrink-0"
                  variant="primary"
                  disabled={!canExport}
                  icon={<Upload className="h-4 w-4" />}
                  onClick={() => a.setConfirming(true)}
                >
                  Nach Banana exportieren
                </Button>
              )}
            </Card>
          </section>

          <section aria-label="Frühere Exporte" className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">
              Frühere Exporte <span className="font-normal text-muted-foreground">({a.batches.length})</span>
            </h2>
            {a.batches.length === 0 ? (
              <Card>
                <EmptyState
                  icon={PackageCheck}
                  title="Noch nichts übergeben"
                  description="Nach dem ersten Export steht hier jeder Stapel — die Datei kann jederzeit erneut geladen werden."
                />
              </Card>
            ) : (
              <BatchList batches={a.batches} onFile={a.downloadFile} onCover={a.downloadCover} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
