"use client";

import useSWR from "swr";
import { Gauge } from "lucide-react";
import { api } from "@/lib/api";
import type { UsageCounter, UsageResponse } from "@/lib/api-schema";
import { istUnbegrenzt, naechsterReset, periodeText, prozent, ton, verbrauchText, warnungen } from "@/lib/usage";
import { PageHeader } from "@/components/ui/page_header";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/Card";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";

const BALKEN: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-destructive",
  neutral: "bg-muted-foreground/40",
};

function Zaehler({ z }: { z: UsageCounter }) {
  const farbe = ton(z);
  const wert = prozent(z);
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle as="h3">{z.label}</CardTitle>
            <CardDescription>{periodeText(z)}</CardDescription>
          </div>
          {z.erreicht && <Badge tone="danger">Erreicht</Badge>}
          {!z.erreicht && z.warnung && <Badge tone="warning">Fast erreicht</Badge>}
          {istUnbegrenzt(z) && <Badge tone="neutral">Unbegrenzt</Badge>}
        </div>

        <p className="mt-4 text-2xl font-semibold tabular-nums text-foreground">{verbrauchText(z)}</p>

        {!istUnbegrenzt(z) && (
          <div
            className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={wert}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${z.label}: ${verbrauchText(z)}`}
          >
            <div className={`h-full rounded-full ${BALKEN[farbe]}`} style={{ width: `${wert}%` }} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AboPage() {
  const { data, error, isLoading, mutate } = useSWR<UsageResponse>("/api/usage", (url: string) =>
    api.get(url).then((r) => r.data)
  );

  const kritisch = data ? warnungen(data.zaehler) : [];

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Gauge}
        title="Abo & Nutzung"
        subtitle="Was in Ihrem Abo enthalten ist und wie viel davon verbraucht ist"
        action={data ? <Badge tone="brand">{data.plan}</Badge> : undefined}
      />

      {isLoading && <PageSkeleton rows={3} />}
      {error && <ErrorState error={error} onRetry={() => mutate()} />}

      {data && (
        <>
          {kritisch.length > 0 && (
            <Card className="border-warning/40">
              <CardContent className="pt-6">
                <CardTitle as="h2">
                  {kritisch[0].erreicht ? "Eine Grenze ist erreicht" : "Eine Grenze ist fast erreicht"}
                </CardTitle>
                <CardDescription>
                  {kritisch.map((z) => `${z.label}: ${verbrauchText(z)}`).join(" · ")}
                  {kritisch.some((z) => z.periode === "monat") &&
                    ` — die monatlichen Zähler beginnen am ${naechsterReset(data.monat_seit)} wieder bei null.`}
                </CardDescription>
              </CardContent>
            </Card>
          )}

          {!data.durchgesetzt && (
            <Card flat className="bg-muted/50">
              <CardContent className="pt-6">
                <CardDescription>
                  Die Grenzen werden zurzeit <strong>nicht durchgesetzt</strong> — es wird gezählt und angezeigt,
                  aber nichts abgelehnt.
                </CardDescription>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.zaehler.map((z) => (
              <Zaehler key={z.key} z={z} />
            ))}
          </div>

          <p className="text-sm text-muted-foreground">
            Monatliche Zähler beginnen am {naechsterReset(data.monat_seit)} wieder bei null. Der Speicherplatz ist
            ein Bestand: er sinkt nur, wenn Belege gelöscht werden.
          </p>
        </>
      )}
    </div>
  );
}
