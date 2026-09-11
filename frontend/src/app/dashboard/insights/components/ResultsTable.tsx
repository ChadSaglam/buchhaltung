import { Search } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import type { Booking } from "@/lib/api";
import { cn } from "@/lib/utils";
import { t } from "@/lib/i18n";

export function ResultsTable({ results, loading }: { results: Booking[]; loading: boolean }) {
  if (loading) return <PageSkeleton rows={5} />;
  if (results.length === 0) {
    return <EmptyState icon={Search} title={t("empty.insights.search")} description={t("empty.insights.search_desc")} />;
  }
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]" aria-label="Suchergebnisse">
          <thead>
            <tr className="border-b border-border bg-muted text-left">
              <th className="px-3 py-3 font-medium text-muted-foreground">Datum</th>
              <th className="px-3 py-3 font-medium text-muted-foreground">Beschreibung</th>
              <th className="px-3 py-3 font-medium text-muted-foreground">Soll</th>
              <th className="px-3 py-3 font-medium text-muted-foreground">Haben</th>
              <th className="px-3 py-3 text-right font-medium text-muted-foreground">Betrag</th>
            </tr>
          </thead>
          <tbody>
            {results.slice(0, 200).map((b) => (
              <tr key={b.id} className="border-b border-border last:border-0 hover:bg-accent transition-colors">
                <td className="whitespace-nowrap px-3 py-2 text-muted-foreground tabular-nums">{b.datum}</td>
                <td className="px-3 py-2 text-foreground">{b.beschreibung}</td>
                <td className="px-3 py-2 font-mono text-brand-600 dark:text-brand-300">{b.kt_soll}</td>
                <td className="px-3 py-2 font-mono text-success">{b.kt_haben}</td>
                <td className={cn("px-3 py-2 text-right font-mono tabular-nums", (Number(b.betrag) || 0) < 0 ? "text-destructive" : "text-foreground")}>
                  {(Number(b.betrag) || 0).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {results.length > 200 && (
        <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
          Zeige die ersten 200 von {results.length} Treffern.
        </p>
      )}
    </Card>
  );
}
