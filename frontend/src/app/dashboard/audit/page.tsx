"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Audit-Protokoll</h1>
          <p className="text-sm text-muted-foreground">
            Nachvollziehbare Aktionen in Ihrem Mandanten
          </p>
        </div>
        {data && (
          <span className="rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold text-brand-700">
            {data.count} Einträge
          </span>
        )}
      </div>

      {isLoading && <MetricCardSkeleton />}

      {error && (
        <p className="text-sm text-destructive">Protokoll konnte nicht geladen werden.</p>
      )}

      {data && data.items.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border py-16 text-center">
          <p className="text-sm text-muted-foreground">Keine Audit-Einträge vorhanden</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Zeitpunkt</th>
                <th className="px-4 py-3">Aktion</th>
                <th className="px-4 py-3">Ziel</th>
                <th className="px-4 py-3">Benutzer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.items.map((entry) => (
                <tr key={entry.id} className="hover:bg-accent/40">
                  <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                    {formatDate(entry.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-md bg-brand-50 px-2 py-0.5 font-medium text-brand-700">
                      {entry.action}
                    </span>
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
      )}
    </div>
  );
}