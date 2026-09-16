import { useState } from "react";
import { EyeOff, Link2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { formatCHF, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { differenceHint, selectedTotal } from "../helpers";
import type { BankTransactionOut, DocumentOut } from "../types";

interface Props {
  transactions: BankTransactionOut[];
  documents: DocumentOut[];
  busy: number | null;
  onIgnore: (id: number) => void;
  onManual: (id: number, documentIds: number[]) => void;
}

/** Bank lines the engine could not explain — the user assigns or ignores them. */
export function OpenLines({ transactions, documents, busy, onIgnore, onManual }: Props) {
  const [picking, setPicking] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const startPicking = (id: number) => {
    setPicking((current) => (current === id ? null : id));
    setSelected(new Set());
  };
  const toggle = (id: number) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <Card>
      <ul className="divide-y divide-border">
        {transactions.map((tx) => {
          const sum = selectedTotal(documents, selected);
          const hint = differenceHint(tx.amount, sum);
          return (
            <li key={tx.id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{tx.description || "Bankzeile"}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(tx.value_date)} ·{" "}
                    <span className="font-mono tabular-nums">{formatCHF(tx.amount, tx.currency)}</span>
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => startPicking(tx.id)}
                    icon={<Link2 className="h-4 w-4" aria-hidden="true" />}
                    aria-expanded={picking === tx.id}
                  >
                    Rechnung wählen
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onIgnore(tx.id)}
                    disabled={busy === tx.id}
                    icon={<EyeOff className="h-4 w-4" aria-hidden="true" />}
                    aria-label={`${tx.description || "Bankzeile"} ignorieren`}
                  >
                    Ignorieren
                  </Button>
                </div>
              </div>

              {picking === tx.id && (
                <div className="mt-3 rounded-lg border border-border p-3">
                  {documents.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Keine offenen Rechnungen vorhanden.</p>
                  ) : (
                    <>
                      <ul className="max-h-56 space-y-1 overflow-y-auto">
                        {documents.map((doc) => (
                          <li key={doc.id}>
                            <label className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 hover:bg-accent">
                              <input
                                type="checkbox"
                                checked={selected.has(doc.id)}
                                onChange={() => toggle(doc.id)}
                                className="h-4 w-4 accent-brand-600"
                              />
                              <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                                {doc.vendor || doc.filename}
                                {doc.invoice_no ? ` · ${doc.invoice_no}` : ""}
                              </span>
                              <span className="font-mono text-sm tabular-nums text-muted-foreground">
                                {formatCHF(doc.amount)}
                              </span>
                            </label>
                          </li>
                        ))}
                      </ul>
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                        <p className={cn("text-xs", hint.ok ? "text-success" : "text-muted-foreground")}>{hint.text}</p>
                        <Button
                          size="sm"
                          variant={hint.ok ? "success" : "primary"}
                          disabled={selected.size === 0 || busy === tx.id}
                          loading={busy === tx.id}
                          onClick={() => {
                            onManual(tx.id, Array.from(selected));
                            setPicking(null);
                            setSelected(new Set());
                          }}
                        >
                          Zuordnen &amp; buchen
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
