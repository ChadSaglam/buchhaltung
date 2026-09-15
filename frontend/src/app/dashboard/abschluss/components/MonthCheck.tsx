"use client";

import { AlertTriangle, CalendarCheck, Landmark, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { formatCHF } from "@/lib/format";
import { useMonatsabschluss } from "../hooks/useMonatsabschluss";
import { differenceText, monthVerdict } from "../helpers";
import { ExportChecklist } from "./ExportChecklist";

/** Abschluss › Monat (B-66): is this month closed, or what is missing? */
export function MonthCheck() {
  const m = useMonatsabschluss();

  if (m.isLoading) return <PageSkeleton rows={3} />;
  if (m.error) return <ErrorState error={m.error} onRetry={m.retry} />;
  if (!m.report) return null;

  const verdict = monthVerdict(m.report.blockers, m.report.warnings);
  const kpis = m.report.kpis;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="monat" className="text-sm text-muted-foreground">
            Monat
          </label>
          <select
            id="monat"
            value={m.selected}
            onChange={(e) => m.setMonat(e.target.value)}
            disabled={m.monate.length === 0}
            className="h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground disabled:opacity-60"
          >
            {m.monate.length === 0 ? (
              <option value={m.selected}>{m.report.label}</option>
            ) : (
              m.monate.map((key) => (
                <option key={key} value={key}>
                  {m.labels[key] ?? key}
                </option>
              ))
            )}
          </select>
        </div>
        <Badge tone={verdict.tone === "success" ? "success" : verdict.tone === "danger" ? "danger" : "warning"}>
          {verdict.text}
        </Badge>
      </div>

      <Card className="p-4">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Buchungen</dt>
            <dd className="mt-1 font-mono text-sm tabular-nums text-foreground">{kpis.buchungen}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Einnahmen</dt>
            <dd className="mt-1 font-mono text-sm tabular-nums text-foreground">{formatCHF(kpis.einnahmen)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">Ausgaben</dt>
            <dd className="mt-1 font-mono text-sm tabular-nums text-foreground">{formatCHF(kpis.ausgaben)}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
              <Landmark className="h-3.5 w-3.5" aria-hidden="true" />
              Bank ↔ 1020
            </dt>
            <dd
              className={`mt-1 text-sm ${Math.abs(kpis.differenz) < 0.005 ? "text-success" : "text-destructive"}`}
            >
              {differenceText(kpis.differenz)}
            </dd>
          </div>
        </dl>
      </Card>

      <ExportChecklist checks={m.report.checks} />

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {m.report.ready ? (
          <ShieldCheck className="h-3.5 w-3.5 text-success" aria-hidden="true" />
        ) : (
          <AlertTriangle className="h-3.5 w-3.5 text-destructive" aria-hidden="true" />
        )}
        <CalendarCheck className="h-3.5 w-3.5" aria-hidden="true" />
        Geprüft wird nur, nichts verändert — die roten Punkte zuerst, dann exportieren.
      </p>
    </div>
  );
}
