import { Wand2, Loader2, Info, TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import type { MonthlyStats } from "@/lib/booking-analytics";
import { chf } from "../helpers";
import type { AiSummaryState, MetricTone } from "../types";

export function SummaryCard({ latest, hasBookings, ai }: {
  latest: MonthlyStats | undefined;
  hasBookings: boolean;
  ai: AiSummaryState;
}) {
  const { summary, summaryFallback, summarizing, runSummary } = ai;
  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Wand2 className="h-4 w-4 text-brand-600 dark:text-brand-300" />
            <h2 className="text-sm font-semibold text-foreground">AI-Monatszusammenfassung</h2>
          </div>
          <Button size="sm" onClick={runSummary} loading={summarizing} disabled={!hasBookings}>
            Erstellen
          </Button>
        </div>

        {latest ? (
          <div className="grid grid-cols-3 gap-3">
            <Metric label="Letzter Monat" value={latest.month} />
            <Metric label="Ausgaben" value={chf(latest.totalDebit)} tone="down" />
            <Metric label="Einnahmen" value={chf(latest.totalCredit)} tone="up" />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Noch keine datierten Buchungen vorhanden.</p>
        )}

        {summarizing && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> AI erstellt die Zusammenfassung…
          </div>
        )}
        {summary && (
          <div className="rounded-lg border border-border bg-surface p-3 text-sm leading-relaxed text-foreground whitespace-pre-wrap">
            {summary}
          </div>
        )}
        {summaryFallback && (
          <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <span>
              Die AI-Zusammenfassung ist nicht verfügbar (Ollama offline). Die Kennzahlen und Auffälligkeiten unten
              basieren weiterhin auf deinen echten Daten.
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: MetricTone }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {tone === "up" && <TrendingUp className="h-3 w-3 text-success" />}
        {tone === "down" && <TrendingDown className="h-3 w-3 text-destructive" />}
        {label}
      </p>
      <p className="mt-1 truncate text-sm font-semibold text-foreground tabular-nums">{value}</p>
    </div>
  );
}
