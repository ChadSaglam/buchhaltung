"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, CircleAlert, Info } from "lucide-react";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import { useApi } from "@/hooks/useApi";
import { useReviewQueue } from "@/hooks/useSystemData";
import type { Schemas } from "@/lib/api-schema";
import { inboxKopf, inboxRows, istAnker, type HeuteRow, type HeuteTone } from "@/lib/heute";
import { cn } from "@/lib/utils";

const TONE_ICON = { danger: CircleAlert, warning: AlertTriangle, info: Info } as const;

const TONE_STYLE: Record<HeuteTone, string> = {
  danger: "border-destructive/30 bg-destructive/5 text-destructive",
  warning: "border-warning/30 bg-warning/5 text-warning",
  info: "border-border bg-surface text-muted-foreground",
};

/**
 * Heute's inbox (`docs/IA-2026-09-14.md`, step 4).
 *
 * Reads the same SWR keys the cards below use, so this costs no extra requests —
 * SWR dedupes by key and both mount in the same burst. What it adds is the
 * answer to "do I have to do anything?", which previously required reading four
 * cards and comparing them.
 */
export function Inbox() {
  const posten = useApi<Schemas["OffenePostenResponse"]>("/api/offene-posten/");
  const abgleich = useApi<Schemas["AbgleichResponse"]>("/api/abgleich/");
  const email = useApi<Schemas["EmailEingangResponse"]>("/api/email/");
  const dauer = useApi<Schemas["DauerbuchungenResponse"]>("/api/dauerbuchungen/");
  const liquiditaet = useApi<Schemas["LiquiditaetResponse"]>("/api/liquiditaet/");
  const usage = useApi<Schemas["UsageResponse"]>("/api/usage");
  const review = useReviewQueue();

  const isLoading =
    posten.isLoading || abgleich.isLoading || email.isLoading || dauer.isLoading || liquiditaet.isLoading;

  // A source that errors contributes no rows. The cards below show their own
  // error state; repeating it here would say "something is broken" three times.
  const rows = inboxRows({
    posten: posten.data,
    abgleich: abgleich.data,
    email: email.data,
    dauer: dauer.data,
    liquiditaet: liquiditaet.data,
    review: review.data,
    usage: usage.data,
  });

  return (
    <section aria-labelledby="inbox-titel">
      <h2 id="inbox-titel" className="mb-4 text-base font-semibold text-foreground">
        {inboxKopf(rows, isLoading)}
      </h2>

      {isLoading ? (
        <div className="space-y-3">
          <MetricCardSkeleton />
          <MetricCardSkeleton />
        </div>
      ) : rows.length === 0 ? (
        <div className="flex items-center gap-3 rounded-xl border border-success/30 bg-success/5 p-5">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden="true" />
          <p className="text-sm text-foreground">
            Nichts liegt an. Neue Belege, Bankzeilen und Fälligkeiten erscheinen hier von selbst.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.id}>
              <Zeile row={row} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Zeile({ row }: { row: HeuteRow }) {
  const Icon = TONE_ICON[row.tone];
  const inhalt = (
    <>
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border",
          TONE_STYLE[row.tone],
        )}
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-foreground">{row.titel}</span>
        <span className="mt-0.5 block text-sm text-muted-foreground">{row.satz}</span>
      </span>
      <span className="flex shrink-0 items-center gap-1.5 text-sm font-medium text-link">
        {row.aktion}
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </span>
    </>
  );

  const klasse =
    "group flex w-full items-center gap-4 rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-[border-color,box-shadow] hover:border-border-strong hover:shadow-md";

  // An anchor row scrolls to the card on this page; there is no route to send
  // the user to, and inventing one would be a page with a single card on it.
  return istAnker(row) ? (
    <a href={row.href} className={klasse}>
      {inhalt}
    </a>
  ) : (
    <Link href={row.href} className={klasse}>
      {inhalt}
    </Link>
  );
}
