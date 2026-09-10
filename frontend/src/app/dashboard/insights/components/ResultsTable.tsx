import { Search, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";
import type { Booking } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ResultsTable({ results, loading }: { results: Booking[]; loading: boolean }) {
  if (loading) {
    return (
      <Card><CardContent className="flex items-center justify-center py-12 text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Laden…</CardContent></Card>
    );
  }
  if (results.length === 0) {
    return <EmptyState icon={Search} title="Keine Treffer" description="Passe deine Suche an oder lösche Filter." />;
  }
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
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
