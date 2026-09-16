"use client";

import Link from "next/link";
import { ArrowRight, Landmark, Receipt, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/shared/ErrorState";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import { useApi } from "@/hooks/useApi";
import { formatCHF } from "@/lib/format";
import {
  QUELLE_LABEL,
  kurzdatum,
  liquiditaetSatz,
  liquiditaetTone,
  naechste,
  steuerSatz,
  type LiquiditaetResponse,
} from "@/lib/liquiditaet";
import { cn } from "@/lib/utils";

const TONE_TEXT = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-destructive",
} as const;

/** Heute: will the money last the quarter, and what belongs to the tax office. */
export function LiquiditaetCard() {
  const { data, isLoading, error, mutate } = useApi<LiquiditaetResponse>("/api/liquiditaet/");

  if (isLoading) return <MetricCardSkeleton />;
  if (error) return <ErrorState error={error} onRetry={() => mutate()} variant="inline" />;
  if (!data) return null;

  const tone = liquiditaetTone(data);
  const steuer = data.steuer;
  const positionen = naechste(data);

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 dark:text-brand-300">
            <Landmark className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold text-foreground">Liquidität 90 Tage</p>
            <p className="text-xs text-muted-foreground">
              bis {kurzdatum(data.bis)}
              {data.stichtag.slice(0, 4) !== data.bis.slice(0, 4) ? data.bis.slice(0, 4) : ""}
            </p>
          </div>
        </div>
        <Badge tone={tone === "danger" ? "danger" : tone === "warning" ? "warning" : "success"}>
          {tone === "danger" ? "eng" : tone === "warning" ? "knapp" : "reicht"}
        </Badge>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3">
        <div>
          <dt className="text-xs text-muted-foreground">Heute</dt>
          <dd className="mt-0.5 font-mono text-sm font-semibold tabular-nums text-foreground">
            {formatCHF(data.stand_heute)}
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-xs text-muted-foreground">
            <TrendingUp className="h-3 w-3" aria-hidden="true" /> Eingang
          </dt>
          <dd className="mt-0.5 font-mono text-sm tabular-nums text-success">{formatCHF(data.eingang)}</dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-xs text-muted-foreground">
            <TrendingDown className="h-3 w-3" aria-hidden="true" /> Ausgang
          </dt>
          <dd className="mt-0.5 font-mono text-sm tabular-nums text-destructive">{formatCHF(data.ausgang)}</dd>
        </div>
      </dl>

      <p className={cn("mt-3 text-xs font-medium", TONE_TEXT[tone])}>{liquiditaetSatz(data)}</p>

      {positionen.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-border pt-3">
          {positionen.map((p, i) => (
            <li key={`${p.datum}-${p.label}-${i}`} className="flex items-baseline justify-between gap-3 text-xs">
              <span className="min-w-0 truncate text-muted-foreground">
                <span className="tabular-nums">{kurzdatum(p.datum)}</span>{" "}
                <span className="text-foreground">{p.label}</span>
                {p.ueberfaellig && <span className="ml-1 text-warning">überfällig</span>}
              </span>
              <span
                className={cn(
                  "shrink-0 font-mono tabular-nums",
                  p.betrag > 0 ? "text-success" : "text-foreground",
                )}
                title={QUELLE_LABEL[p.quelle] ?? p.quelle}
              >
                {p.betrag > 0 ? "+" : "−"}
                {formatCHF(Math.abs(p.betrag))}
              </span>
            </li>
          ))}
        </ul>
      )}

      {steuer && (
        <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                <Receipt className="h-3.5 w-3.5" aria-hidden="true" /> Steuerrückstellung {steuer.jahr}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Gewinn seit 1.1.: <span className="font-mono tabular-nums">{formatCHF(steuer.gewinn)}</span>
                {steuer.satz != null && <> · Satz {steuer.satz.toFixed(2)} %</>}
              </p>
            </div>
            {steuer.satz != null && (steuer.pro_quartal ?? 0) > 0 && (
              <span className="shrink-0 font-mono text-sm font-semibold tabular-nums text-foreground">
                {formatCHF(steuer.pro_quartal)}
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{steuerSatz(steuer)}</p>
          {steuer.satz == null ? (
            <>
              <p className="mt-1 text-xs text-muted-foreground">{steuer.hinweis}</p>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{steuer.quelle}</p>
              <Link
                href="/dashboard/rechnungen/firma"
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-link hover:underline"
              >
                Satz hinterlegen <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </>
          ) : (
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{steuer.hinweis}</p>
          )}
        </div>
      )}

      {data.warnungen.length > 0 && (
        <ul className="mt-3 space-y-1">
          {data.warnungen.map((w) => (
            <li key={w} className="text-[11px] leading-snug text-muted-foreground">
              {w}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
