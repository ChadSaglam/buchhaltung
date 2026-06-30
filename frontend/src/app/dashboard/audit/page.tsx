"use client";

import useSWR from "swr";
import { ScrollText } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page_header";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";

interface AuditEntry {
  id: number;
  action: string;
  actor_user_id: number | null;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string | null;
}

interface AuditResponse {
  count: number;
  items: AuditEntry[];
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-CH", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AuditPage() {
  const { data, error, isLoading } = useSWR<AuditResponse>("/api/audit/", (url: string) =>
    api.get(url).then((r) => r.data)
  );

  return (
    <div className="space-y-6">
      <PageHeader
        icon={ScrollText}
        title="Audit-Protokoll"
        subtitle="Nachvollziehbare Aktionen in Ihrem Mandanten"
        action={
          data ? (
            <Badge tone="neutral">{data.count} Einträge</Badge>
          ) : undefined
        }
      />

      {isLoading && <MetricCardSkeleton />}

      {error && (
        <p className="text-sm text-destructive">Protokoll konnte nicht geladen werden.</p>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={ScrollText}
          title="Keine Audit-Einträge"
          description="Sobald Aktionen ausgeführt werden, erscheinen sie hier."
        />
      )}

      {data && data.items.length > 0 && (
        <Card>
          <div className="overflow-hidden rounded-xl">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Zeitpunkt</th>
                  <th className="px-4 py-3">Aktion</th>
                  <th className="px-4 py-3">Ziel</th>
                  <th className="px-4 py-3">Benutzer</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((entry) => (
                  <tr key={entry.id} className="hover:bg-accent/40 transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap text-muted-foreground tabular-nums">
                      {formatDate(entry.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone="brand">{entry.action}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {entry.target_type ? `${entry.target_type} #${entry.target_id ?? "—"}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {entry.actor_user_id ?? "System"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
