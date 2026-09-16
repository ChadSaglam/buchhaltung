"use client";

import { CheckCheck, FileText, Landmark, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { MetricCard } from "@/components/ui/metric_card";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { formatCHF } from "@/lib/format";
import { useAbgleich } from "./hooks/useAbgleich";
import { StatementDropZone } from "./components/StatementDropZone";
import { ProposalCard } from "./components/ProposalCard";
import { OpenLines } from "./components/OpenLines";

export default function AbgleichPage() {
  const a = useAbgleich();

  return (
    <div className="space-y-6">
      <PageHeader
        icon={CheckCheck}
        title="Abgleich"
        subtitle="Welche Bankzeile hat welche Rechnung bezahlt — bestätigen, dann ist es gebucht"
      />

      <StatementDropZone onFile={a.uploadStatement} uploading={a.uploading} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard
          title="Vorschläge"
          value={a.summary.vorschlaege}
          subtitle={a.summary.exakt ? `${a.summary.exakt} über die Referenz — sicher` : "zum Bestätigen"}
          icon={<ShieldCheck className="h-5 w-5" />}
          accent={a.summary.vorschlaege ? "brand" : "neutral"}
        />
        <MetricCard
          title="Offene Bankzeilen"
          value={a.summary.offene_zeilen}
          subtitle="noch keiner Rechnung zugeordnet"
          icon={<Landmark className="h-5 w-5" />}
          accent={a.summary.offene_zeilen ? "warning" : "success"}
        />
        <MetricCard
          title="Offene Rechnungen"
          value={a.summary.offene_dokumente}
          subtitle="warten auf eine Zahlung"
          icon={<FileText className="h-5 w-5" />}
          accent="info"
        />
      </div>

      {a.isLoading ? (
        <PageSkeleton rows={4} />
      ) : a.error ? (
        <ErrorState error={a.error} onRetry={a.retry} />
      ) : (
        <>
          <section aria-label="Vorschläge" className="space-y-3">
            {a.items.length === 0 ? (
              <Card>
                <EmptyState
                  icon={CheckCheck}
                  title="Nichts abzugleichen"
                  description="Lade einen Kontoauszug hoch oder erfasse Rechnungen — Vorschläge erscheinen hier automatisch."
                />
              </Card>
            ) : (
              <div role="listbox" aria-label="Abgleich-Vorschläge" className="space-y-3">
                {a.items.map((item, index) => (
                  <ProposalCard
                    key={item.transaction.id}
                    item={item}
                    active={index === a.selected}
                    busy={a.busy === item.transaction.id}
                    onSelect={() => a.setSelected(index)}
                    onConfirm={() => a.confirm(item.transaction.id)}
                    onReject={() => a.reject(item.transaction.id)}
                  />
                ))}
                <p className="text-xs text-muted-foreground">
                  Tastatur: <kbd className="rounded border border-border px-1">j</kbd>/
                  <kbd className="rounded border border-border px-1">k</kbd> wählen ·{" "}
                  <kbd className="rounded border border-border px-1">a</kbd> stimmt ·{" "}
                  <kbd className="rounded border border-border px-1">r</kbd> passt nicht
                </p>
              </div>
            )}
          </section>

          {a.openTransactions.length > 0 && (
            <section aria-label="Offene Bankzeilen" className="space-y-2">
              <h2 className="text-sm font-semibold text-foreground">
                Offene Bankzeilen <span className="font-normal text-muted-foreground">({a.openTransactions.length})</span>
              </h2>
              <OpenLines
                transactions={a.openTransactions}
                documents={a.openDocuments}
                busy={a.busy}
                onIgnore={a.ignore}
                onManual={a.matchManually}
              />
            </section>
          )}

          {a.openDocuments.length > 0 && (
            <section aria-label="Offene Rechnungen" className="space-y-2">
              <h2 className="text-sm font-semibold text-foreground">
                Offene Rechnungen <span className="font-normal text-muted-foreground">({a.openDocuments.length})</span>
              </h2>
              <Card>
                <ul className="divide-y divide-border">
                  {a.openDocuments.map((doc) => (
                    <li key={doc.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                      <span className="min-w-0 truncate text-sm text-foreground">
                        {doc.vendor || doc.filename}
                        {doc.invoice_no ? <span className="text-muted-foreground"> · {doc.invoice_no}</span> : null}
                      </span>
                      <span className="font-mono text-sm tabular-nums text-muted-foreground">{formatCHF(doc.amount)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          )}
        </>
      )}
    </div>
  );
}
