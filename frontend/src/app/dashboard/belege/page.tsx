"use client";

import { Receipt, AlertTriangle, CheckCircle2, Clock, FilePlus2 } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { ButtonLink } from "@/components/ui/Button";
import { MetricCard } from "@/components/ui/metric_card";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { cn } from "@/lib/utils";
import { useRechnungen } from "./hooks/useRechnungen";
import { BulkDropZone } from "./components/BulkDropZone";
import { DocumentTable } from "./components/DocumentTable";
import { VersandDialog } from "@/app/dashboard/components/VersandDialog";
import { useVersand } from "./hooks/useVersand";
import { STATUS_LABEL, formatCHF } from "./helpers";
import type { DocumentStatus } from "./types";

const FILTERS: (DocumentStatus | "alle")[] = ["alle", "offen", "bezahlt", "exportiert", "fehler"];

export default function RechnungenPage() {
  const r = useRechnungen();
  const versand = useVersand(() => r.retry());
  const s = r.summary;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Receipt}
        title="Rechnungen"
        subtitle="Rechnungen sammeln → offene Posten im Blick → beim Kontoauszug abgleichen"
        action={
          <ButtonLink href="/dashboard/belege/neu" icon={<FilePlus2 className="h-4 w-4" />}>
            Rechnung schreiben
          </ButtonLink>
        }
      />

      <BulkDropZone onFiles={r.upload} uploading={r.uploading} progress={r.progress} />

      {s && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <MetricCard title="Offen" value={formatCHF(s.offen_betrag)} subtitle={`${s.offen} Rechnung${s.offen === 1 ? "" : "en"}`} icon={<Clock className="h-5 w-5" />} accent="warning" />
          <MetricCard title="Überfällig" value={s.ueberfaellig} subtitle="Fälligkeitsdatum überschritten" icon={<AlertTriangle className="h-5 w-5" />} accent={s.ueberfaellig ? "danger" : "neutral"} />
          <MetricCard title="Bezahlt" value={s.bezahlt} subtitle={s.fehler ? `${s.fehler} mit Fehler` : "abgeglichen"} icon={<CheckCircle2 className="h-5 w-5" />} accent="success" />
        </div>
      )}

      {r.isLoading ? (
        <PageSkeleton rows={4} />
      ) : r.error ? (
        <ErrorState error={r.error} onRetry={r.retry} />
      ) : (
        <>
          <div role="tablist" aria-label="Status-Filter" className="flex flex-wrap gap-1">
            {FILTERS.map((f) => (
              <button
                key={f}
                role="tab"
                aria-selected={r.filter === f}
                onClick={() => r.setFilter(f)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  r.filter === f ? "bg-brand-500/12 text-brand-600 dark:text-brand-300" : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                {f === "alle" ? "Alle" : STATUS_LABEL[f]}
              </button>
            ))}
          </div>
          {r.items.length === 0 ? (
            <EmptyState icon={Receipt} title="Noch keine Rechnungen" description="Lege Rechnungen oben ab — QR-Rechnungen werden sofort exakt erfasst." />
          ) : (
            <DocumentTable
              items={r.items}
              onStatus={r.setStatus}
              onSenden={(doc) => versand.oeffnen(doc.id)}
              sendenLoadingId={versand.loadingId}
            />
          )}
        </>
      )}

      <VersandDialog
        draft={versand.draft}
        sending={versand.sending}
        onClose={versand.schliessen}
        onSend={versand.senden}
      />
    </div>
  );
}
