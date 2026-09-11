import { Check, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { confidenceTone } from "../helpers";
import type { TxRow } from "../types";

const COLS = ["Nr", "Datum", "Beschreibung", "KtSoll", "KtHaben", "Betrag CHF", "MwSt", "AI", "Vorschlag"];
const CELL = "bg-transparent focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5";

interface Props {
  rows: TxRow[];
  onUpdate: (idx: number, field: keyof TxRow, value: string | number) => void;
  onAccept: (idx: number) => void;
}

export function TransactionTable({ rows, onUpdate, onAccept }: Props) {
  const field = (i: number, r: TxRow, key: keyof TxRow, cls: string, label: string) => (
    <input
      aria-label={`${label} Zeile ${r.Nr}`}
      value={String(r[key] ?? "")}
      onChange={(e) => onUpdate(i, key, e.target.value)}
      className={`${CELL} ${cls}`}
    />
  );
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[800px]" aria-label="Transaktionen aus dem Kontoauszug">
          <thead>
            <tr className="bg-muted border-b border-border text-left">
              {COLS.map((h) => (
                <th key={h} scope="col" className="px-3 py-3 font-medium text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const conf = confidenceTone(r.confidence);
              return (
                <tr key={r.Nr} className="border-b border-border last:border-0 hover:bg-accent transition-colors">
                  <td className="px-3 py-2 text-muted-foreground w-12 tabular-nums">{r.Nr}</td>
                  <td className="px-3 py-2">{field(i, r, "Datum", "w-24 text-foreground", "Datum")}</td>
                  <td className="px-3 py-2">{field(i, r, "Beschreibung", "w-full min-w-[200px] text-foreground", "Beschreibung")}</td>
                  <td className="px-3 py-2">{field(i, r, "KtSoll", "w-16 font-mono text-brand-600 dark:text-brand-300", "KtSoll")}</td>
                  <td className="px-3 py-2">{field(i, r, "KtHaben", "w-16 font-mono text-success", "KtHaben")}</td>
                  <td className="px-3 py-2 font-mono text-right tabular-nums text-foreground">{(r["Betrag CHF"] || 0).toFixed(2)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {field(i, r, "MwStUSt-Code", "w-12 text-foreground", "MwSt-Code")}
                    {r["MwSt-%"] && <span className="ml-1 text-xs text-muted-foreground tabular-nums">{r["MwSt-%"]}</span>}
                  </td>
                  <td className="px-3 py-2">
                    <span title={r.source ? `Quelle: ${r.source}` : undefined} className="inline-flex">
                      <Badge tone={conf.tone}>{conf.label}</Badge>
                    </span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.accepted ? (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
                        <Check className="h-3.5 w-3.5" aria-hidden="true" /> Übernommen
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onAccept(i)}
                        className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
                        aria-label={`AI-Vorschlag für Zeile ${r.Nr} übernehmen`}
                      >
                        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Übernehmen
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
