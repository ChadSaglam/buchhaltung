"use client";

import Link from "next/link";
import { ArrowRight, BellRing, HandCoins, Wallet } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/shared/ErrorState";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import { formatCHF, formatDate } from "@/lib/format";
import { bucketRows, mahnungHistory, mahnungLabel, overdueLabel, overdueTone, urgentItems } from "@/lib/offene-posten";
import type { OpenItemOut, SideOut } from "@/lib/offene-posten";
import { useOffenePosten } from "../hooks/useOffenePosten";
import { MahnungDialog } from "./MahnungDialog";

function SideBlock({
  title,
  subtitle,
  icon,
  side,
  onMahnung,
  loadingId,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  side: SideOut | undefined;
  onMahnung?: (item: OpenItemOut) => void;
  loadingId?: number | null;
}) {
  const items = urgentItems(side);
  const buckets = bucketRows(side);

  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 [&_svg]:h-4 [&_svg]:w-4 dark:text-brand-300">
            {icon}
          </span>
          <div>
            <p className="text-sm font-semibold text-foreground">{title}</p>
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-mono text-sm font-semibold tabular-nums text-foreground">{formatCHF(side?.total ?? 0)}</p>
          <p className="text-xs text-muted-foreground">
            {side?.overdue_count
              ? `${formatCHF(side.overdue_total)} überfällig`
              : `${side?.count ?? 0} offen`}
          </p>
        </div>
      </div>

      {buckets.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {buckets.map((b) => (
            <li key={b.key}>
              <Badge tone={b.key === "nicht_faellig" ? "neutral" : b.key === "1_30" ? "warning" : "danger"}>
                {b.label}: {formatCHF(b.amount)}
              </Badge>
            </li>
          ))}
        </ul>
      )}

      {items.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Nichts offen — schön.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {items.map((item) => {
            const history = mahnungHistory(item);
            return (
              <li key={item.document.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {item.document.vendor || item.document.filename}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {item.document.invoice_no ? `${item.document.invoice_no} · ` : ""}
                    fällig {formatDate(item.due_date)}
                    {history ? ` · ${history}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="font-mono text-sm tabular-nums text-foreground">{formatCHF(item.document.amount)}</span>
                  <Badge tone={overdueTone(item.days_overdue)}>{overdueLabel(item.days_overdue)}</Badge>
                  {onMahnung && item.mahnbar && (
                    <Button
                      size="xs"
                      variant="secondary"
                      icon={<BellRing className="h-3.5 w-3.5" />}
                      loading={loadingId === item.document.id}
                      onClick={() => onMahnung(item)}
                    >
                      {mahnungLabel(item.document.mahnstufe ?? 0)}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** "Wer schuldet uns / was schulden wir" — the weekly question, on Heute (B-65). */
export function OffenePostenCard() {
  const o = useOffenePosten();

  if (o.isLoading) return <MetricCardSkeleton />;
  if (o.error) return <ErrorState error={o.error} onRetry={o.retry} variant="inline" />;

  return (
    <>
      <Card className="p-5">
        <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
          <SideBlock
            title="Wer schuldet uns"
            subtitle="Debitoren — eigene Rechnungen"
            icon={<HandCoins />}
            side={o.debitoren}
            onMahnung={o.openDraft}
            loadingId={o.loadingId}
          />
          <div className="hidden w-px shrink-0 bg-border lg:block" aria-hidden="true" />
          <SideBlock
            title="Was schulden wir"
            subtitle="Kreditoren — Lieferantenrechnungen"
            icon={<Wallet />}
            side={o.kreditoren}
          />
        </div>
        <div className="mt-4 border-t border-border pt-3">
          <Link
            href="/dashboard/rechnungen"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-link hover:underline"
          >
            Alle Rechnungen ansehen
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </div>
      </Card>

      <MahnungDialog
        draft={o.draft}
        recording={o.recording}
        onClose={o.closeDraft}
        onRecord={o.recordSent}
        onPrint={o.openLetter}
      />
    </>
  );
}
