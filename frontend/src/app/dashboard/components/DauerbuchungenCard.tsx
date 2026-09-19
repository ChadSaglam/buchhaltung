"use client";

import { CalendarClock } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/shared/ErrorState";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import { useApi } from "@/hooks/useApi";
import { formatCHF } from "@/lib/format";
import {
  STATUS_LABEL,
  STATUS_TONE,
  fehltSatz,
  kopfTone,
  kopfzeile,
  tagLabel,
  type DauerStatus,
  type DauerbuchungenResponse,
} from "@/lib/dauerbuchungen";
import { cn } from "@/lib/utils";

const TONE_TEXT = { success: "text-success", warning: "text-warning", neutral: "text-muted-foreground" } as const;

/** Heute: what goes out every month, and what has not gone out yet (B-74). */
export function DauerbuchungenCard() {
  const { data, isLoading, error, mutate } = useApi<DauerbuchungenResponse>("/api/dauerbuchungen/");

  if (isLoading) return <MetricCardSkeleton />;
  if (error) return <ErrorState error={error} onRetry={() => mutate()} variant="inline" />;
  if (!data || (data.eintraege ?? []).length === 0) return null;

  const tone = kopfTone(data);
  const fehlen = data.fehlen ?? [];

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 dark:text-brand-300">
            <CalendarClock className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold text-foreground">Jeden Monat</p>
            <p className={cn("text-xs", TONE_TEXT[tone])}>{kopfzeile(data)}</p>
          </div>
        </div>
        <span className="shrink-0 font-mono text-sm tabular-nums text-muted-foreground">
          {formatCHF(data.monatstotal)}
        </span>
      </div>

      {fehlen.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-lg border border-warning/30 bg-warning/10 p-3">
          {fehlen.map((entry) => (
            <li key={entry.schluessel || entry.label} className="text-xs text-foreground">
              {fehltSatz(entry)}
            </li>
          ))}
        </ul>
      )}

      <ul className="mt-4 space-y-1.5 border-t border-border pt-3">
        {(data.eintraege ?? []).map((entry) => (
          <li key={entry.schluessel || entry.label} className="flex items-baseline justify-between gap-3 text-xs">
            <span className="min-w-0 truncate text-muted-foreground">
              <span className="text-foreground">{entry.label}</span> {tagLabel(entry)}
            </span>
            <span className="flex shrink-0 items-center gap-2">
              <Badge tone={STATUS_TONE[entry.status as DauerStatus] ?? "neutral"}>
                {STATUS_LABEL[entry.status as DauerStatus] ?? entry.status}
              </Badge>
              <span className="font-mono tabular-nums text-foreground">{formatCHF(entry.betrag)}</span>
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        Aus den eigenen Buchungen erkannt — mindestens drei Monate mit demselben Betrag. Nichts davon wird
        automatisch gebucht.
      </p>
    </Card>
  );
}
