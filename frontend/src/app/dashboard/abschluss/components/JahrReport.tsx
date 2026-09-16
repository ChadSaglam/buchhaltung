"use client";

import { Download, FileText } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { formatCHF } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useJahr } from "../hooks/useJahr";
import { ExportChecklist } from "./ExportChecklist";
import type { JahrGruppe } from "../types";

function Zeilen({ gruppe, total }: { gruppe: JahrGruppe; total?: string }) {
  return (
    <>
      {gruppe.positionen.map((p) => (
        <tr key={`${gruppe.key}-${p.konto}`} className="border-b border-border/60 last:border-0">
          <td className="py-1.5 pr-3 font-mono text-xs text-muted-foreground">{p.konto}</td>
          <td className="py-1.5 pr-3">{p.bezeichnung || "—"}</td>
          <td className="py-1.5 text-right tabular-nums">{formatCHF(p.saldo)}</td>
        </tr>
      ))}
      {total && (
        <tr className="border-t border-border font-semibold">
          <td className="py-1.5 pr-3" />
          <td className="py-1.5 pr-3">{total}</td>
          <td className="py-1.5 text-right tabular-nums">{formatCHF(gruppe.total)}</td>
        </tr>
      )}
    </>
  );
}

export function JahrReport() {
  const j = useJahr();
  const r = j.report;

  if (j.isLoading) return <PageSkeleton rows={3} />;
  if (j.error) return <ErrorState error={j.error} onRetry={j.retry} />;
  if (!r || r.buchungen === 0) {
    return (
      <Card>
        <EmptyState
          icon={FileText}
          title="Noch keine Buchungen in diesem Jahr"
          description="Sobald Belege gebucht sind, stehen hier Bilanz, Erfolgsrechnung und der Abschreibungsvorschlag."
        />
      </Card>
    );
  }

  return (
    <Card className="space-y-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Jahr wählen">
          {j.jahre.map((year) => (
            <button
              key={year}
              role="tab"
              aria-selected={year === r.jahr}
              onClick={() => j.setJahr(year)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                year === r.jahr
                  ? "bg-brand-500/12 text-brand-600 dark:text-brand-300"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              {year}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<FileText className="h-4 w-4" />}
            loading={j.busy === "pdf"}
            onClick={j.pdfHolen}
          >
            PDF
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<Download className="h-4 w-4" />}
            loading={j.busy === "zip"}
            onClick={j.paketHolen}
          >
            Paket für den Treuhänder
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-foreground">Bilanz per 31.12.{r.jahr}</h3>
            <span className="text-xs text-muted-foreground">{r.buchungen} Buchungen</span>
          </div>
          <table className="w-full text-sm">
            <tbody>
              <Zeilen gruppe={r.aktiven} total="Total Aktiven" />
              <tr>
                <td colSpan={3} className="h-3" />
              </tr>
              <Zeilen gruppe={r.passiven} total="Total Passiven" />
              <tr className="font-semibold">
                <td className="py-1.5 pr-3" />
                <td className="py-1.5 pr-3">Gewinn {r.jahr}</td>
                <td className="py-1.5 text-right tabular-nums">{formatCHF(r.gewinn)}</td>
              </tr>
            </tbody>
          </table>
          {Math.abs(r.bilanz_differenz) > 0.005 && (
            <p className="mt-3 text-xs text-muted-foreground">
              Differenz {formatCHF(r.bilanz_differenz)} — normal, solange keine Eröffnungsbilanz erfasst ist.
              Das System bucht ab dem ersten Beleg und kennt die Anfangsbestände nicht.
            </p>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold text-foreground">Erfolgsrechnung {r.jahr}</h3>
          <table className="w-full text-sm">
            <tbody>
              {r.ertrag.map((g) => (
                <Zeilen key={g.key} gruppe={g} />
              ))}
              <tr className="border-t border-border font-semibold">
                <td className="py-1.5 pr-3" />
                <td className="py-1.5 pr-3">Total Ertrag</td>
                <td className="py-1.5 text-right tabular-nums">{formatCHF(r.ertrag_total)}</td>
              </tr>
              {r.aufwand.map((g) => (
                <Zeilen key={g.key} gruppe={g} />
              ))}
              <tr className="border-t border-border font-semibold">
                <td className="py-1.5 pr-3" />
                <td className="py-1.5 pr-3">Total Aufwand</td>
                <td className="py-1.5 text-right tabular-nums">{formatCHF(r.aufwand_total)}</td>
              </tr>
              <tr className="border-t border-border text-base font-bold">
                <td className="py-2 pr-3" />
                <td className="py-2 pr-3">Gewinn</td>
                <td className="py-2 text-right tabular-nums">{formatCHF(r.gewinn)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {r.abschreibungen.length > 0 && (
        <div>
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-sm font-semibold text-foreground">Abschreibungsvorschlag</h3>
            <Badge tone="neutral">{r.abschreibungen[0].quelle}</Badge>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {r.abschreibungen.map((a) => (
                <tr key={a.konto} className="border-b border-border/60 last:border-0">
                  <td className="py-1.5 pr-3 font-mono text-xs text-muted-foreground">{a.konto}</td>
                  <td className="py-1.5 pr-3">{a.bezeichnung}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums text-muted-foreground">
                    {formatCHF(a.buchwert)}
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums text-muted-foreground">{a.satz} %</td>
                  <td className="py-1.5 text-right tabular-nums font-medium">{formatCHF(a.betrag)}</td>
                </tr>
              ))}
              <tr className="border-t border-border font-semibold">
                <td className="py-1.5 pr-3" colSpan={4}>
                  Total (Buchung {r.abschreibungen[0].kt_soll} an Anlagekonto, per 31.12.)
                </td>
                <td className="py-1.5 text-right tabular-nums">{formatCHF(r.abschreibungen_total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-sm font-semibold text-foreground">Prüfliste</h3>
        <ExportChecklist checks={r.checks} />
      </div>
    </Card>
  );
}
