import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { chf, zeilenbetrag, type Totals } from "../helpers";
import type { PositionRow } from "../types";

const INPUT =
  "w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring";

export function PositionenEditor({ rows, summe, onChange, onAdd, onRemove }: {
  rows: PositionRow[];
  summe: Totals;
  onChange: (index: number, field: keyof PositionRow, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  return (
    <section aria-labelledby="positionen-titel" className="rounded-xl border border-border bg-card p-6">
      <h2 id="positionen-titel" className="text-base font-semibold text-foreground">Positionen</h2>
      <p className="mt-0.5 mb-4 text-sm text-muted-foreground">Preise ohne MWST — die Steuer kommt unten dazu.</p>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="py-2 pr-3 font-medium">Bezeichnung</th>
              <th scope="col" className="py-2 pr-3 font-medium">Menge</th>
              <th scope="col" className="py-2 pr-3 font-medium">Einheit</th>
              <th scope="col" className="py-2 pr-3 font-medium">Einzelpreis</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Betrag</th>
              <th scope="col" className="py-2"><span className="sr-only">Entfernen</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-b border-border/60 last:border-0">
                <td className="py-2 pr-3">
                  <input
                    aria-label={`Bezeichnung Position ${index + 1}`}
                    value={row.bezeichnung}
                    onChange={(e) => onChange(index, "bezeichnung", e.target.value)}
                    placeholder="Beratung September"
                    className={INPUT}
                  />
                </td>
                <td className="w-24 py-2 pr-3">
                  <input
                    aria-label={`Menge Position ${index + 1}`}
                    inputMode="decimal"
                    value={row.menge}
                    onChange={(e) => onChange(index, "menge", e.target.value)}
                    className={INPUT}
                  />
                </td>
                <td className="w-24 py-2 pr-3">
                  <input
                    aria-label={`Einheit Position ${index + 1}`}
                    value={row.einheit}
                    onChange={(e) => onChange(index, "einheit", e.target.value)}
                    placeholder="h"
                    className={INPUT}
                  />
                </td>
                <td className="w-32 py-2 pr-3">
                  <input
                    aria-label={`Einzelpreis Position ${index + 1}`}
                    inputMode="decimal"
                    value={row.einzelpreis}
                    onChange={(e) => onChange(index, "einzelpreis", e.target.value)}
                    placeholder="150.00"
                    className={INPUT}
                  />
                </td>
                <td className="w-28 py-2 pr-3 text-right tabular-nums text-foreground">{chf(zeilenbetrag(row))}</td>
                <td className="w-10 py-2 text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Position ${index + 1} entfernen`}
                    disabled={rows.length === 1}
                    onClick={() => onRemove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <Button variant="secondary" size="sm" icon={<Plus className="h-4 w-4" />} onClick={onAdd}>
          Position hinzufügen
        </Button>
        <dl className="w-full text-sm sm:w-64">
          <div className="flex justify-between py-1">
            <dt className="text-muted-foreground">Zwischentotal</dt>
            <dd className="tabular-nums text-foreground">{chf(summe.netto)}</dd>
          </div>
          {summe.satz > 0 && (
            <div className="flex justify-between py-1">
              <dt className="text-muted-foreground">MWST {summe.satz.toFixed(1)} %</dt>
              <dd className="tabular-nums text-foreground">{chf(summe.mwst)}</dd>
            </div>
          )}
          <div className="mt-1 flex justify-between border-t border-border pt-2 font-semibold">
            <dt className="text-foreground">Total CHF</dt>
            <dd className="tabular-nums text-foreground">{chf(summe.total)}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
