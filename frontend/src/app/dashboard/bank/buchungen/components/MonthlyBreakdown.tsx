import { Card, CardContent } from "@/components/ui/Card";
import type { MonthlyStats } from "@/lib/booking-analytics";

export function MonthlyBreakdown({ months }: { months: MonthlyStats[] }) {
  if (months.length === 0) return null;
  return (
    <Card>
      <CardContent>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Monatsübersicht</h2>
        <div className="space-y-2">
          {months.slice(0, 6).map((m) => {
            const max = Math.max(...months.slice(0, 6).map((x) => x.totalDebit + x.totalCredit), 1);
            const w = ((m.totalDebit + m.totalCredit) / max) * 100;
            return (
              <div key={m.month} className="flex items-center gap-3">
                <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground tabular-nums">{m.month}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${w}%` }} />
                </div>
                <span className="w-16 shrink-0 text-right text-xs text-muted-foreground tabular-nums">{m.count}×</span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
