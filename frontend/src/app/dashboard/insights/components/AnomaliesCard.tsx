import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { Anomaly } from "@/lib/booking-analytics";
import { chf } from "../helpers";

export function AnomaliesCard({ anomalies, loading }: { anomalies: Anomaly[]; loading: boolean }) {
  return (
    <Card>
      <CardContent>
        <div className="mb-3 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-warning" />
          <h2 className="text-sm font-semibold text-foreground">Auffälligkeiten</h2>
          {anomalies.length > 0 && <Badge tone="warning">{anomalies.length}</Badge>}
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Analysiere…</p>
        ) : anomalies.length === 0 ? (
          <p className="text-sm text-muted-foreground">Keine Auffälligkeiten erkannt.</p>
        ) : (
          <ul className="space-y-2">
            {anomalies.slice(0, 12).map((a) => (
              <li key={a.booking.id} className="rounded-lg border border-border bg-surface p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium text-foreground">{a.booking.beschreibung || "—"}</span>
                  <Badge tone={a.severity === "high" ? "danger" : "warning"}>
                    {a.severity === "high" ? "Hoch" : "Mittel"}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{a.reason}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground tabular-nums">
                  {a.booking.datum} · {chf(Math.abs(Number(a.booking.betrag) || 0))}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
