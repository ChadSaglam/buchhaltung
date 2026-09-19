"use client";

import Link from "next/link";
import { ArrowRight, Mail, MailWarning } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { useApi } from "@/hooks/useApi";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import type { EmailEingang } from "@/app/dashboard/belege/email/types";
import { belegeTitel } from "@/app/dashboard/belege/email/helpers";

/** Heute: "3 neue Belege per E-Mail" — and the one thing that blocks the rest. */
export function EmailEingangCard() {
  const { data, isLoading, error } = useApi<EmailEingang>("/api/email/");

  if (isLoading) return <MetricCardSkeleton />;
  if (error || !data) return null;

  const { einstellungen: s, belege_24h: belege, abgelehnt } = data;
  const wartet = s.bereit && (s.absender ?? []).length === 0;

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 dark:text-brand-300">
            <Mail className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold text-foreground">{belegeTitel(belege)}</p>
            <p className="text-xs text-muted-foreground">
              {s.bereit ? s.adresse : "Noch keine Adresse eingerichtet"}
            </p>
          </div>
        </div>
        {abgelehnt > 0 && (
          <Badge tone="warning">
            <MailWarning className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
            {abgelehnt} abgelehnt
          </Badge>
        )}
      </div>

      {wartet && (
        <p className="mt-3 text-xs text-muted-foreground">
          Solange kein Absender freigegeben ist, wird nichts übernommen.
        </p>
      )}

      <div className="mt-4 border-t border-border pt-3">
        <Link
          href="/dashboard/belege/email"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-link hover:underline"
        >
          E-Mail-Eingang öffnen
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>
    </Card>
  );
}
