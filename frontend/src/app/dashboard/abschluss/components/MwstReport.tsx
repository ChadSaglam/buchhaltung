"use client";

import { Check, Copy, Download, Receipt } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { formatCHF } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useMwst } from "../hooks/useMwst";
import { MWST_TOTAL_ZIFFERN, isEmptyZiffer, methodeLabel, mwstVerdict } from "../helpers";
import { ExportChecklist } from "./ExportChecklist";

/** Abschluss › Quartal (B-67): Formular 200 aus den Buchungen, als Entwurf. */
export function MwstReport() {
  const m = useMwst();

  if (m.isLoading) return <PageSkeleton rows={3} />;
  if (m.error) return <ErrorState error={m.error} onRetry={m.retry} />;
  if (!m.report) return null;

  const verdict = mwstVerdict(m.report.zu_bezahlen, m.report.guthaben);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="quartal" className="text-sm text-muted-foreground">
            Quartal
          </label>
          <select
            id="quartal"
            value={m.selected}
            onChange={(e) => m.setQuartal(e.target.value)}
            disabled={m.quartale.length === 0}
            className="h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground disabled:opacity-60"
          >
            {m.quartale.length === 0 ? (
              <option value={m.selected}>{m.report.quartal}</option>
            ) : (
              m.quartale.map((key) => (
                <option key={key} value={key}>
                  {key} · {m.labels[key] ?? ""}
                </option>
              ))
            )}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="methode" className="text-sm text-muted-foreground">
            Methode
          </label>
          <select
            id="methode"
            value={m.methode}
            onChange={(e) => m.setMethode(e.target.value as "effektiv" | "saldo")}
            className="h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground"
          >
            <option value="effektiv">Effektiv</option>
            <option value="saldo">Saldosteuersatz</option>
          </select>
        </div>

        {m.methode === "saldo" && (
          <div className="flex items-center gap-2">
            <label htmlFor="satz" className="text-sm text-muted-foreground">
              Satz %
            </label>
            <input
              id="satz"
              type="number"
              step="0.1"
              min="0.1"
              max="15"
              value={m.satz}
              onChange={(e) => m.setSatz(e.target.value)}
              className="h-9 w-20 rounded-lg border border-border bg-card px-3 text-sm text-foreground"
            />
          </div>
        )}

        <Badge tone={verdict.tone === "danger" ? "danger" : verdict.tone === "success" ? "success" : "neutral"}>
          {verdict.text}
        </Badge>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" aria-label={`MWST-Abrechnung ${m.report.quartal}`}>
            <caption className="px-4 pt-3 text-left text-xs text-muted-foreground">
              {methodeLabel(m.report.methode, m.report.satz)} · {m.report.zeitraum} · {m.report.buchungen}{" "}
              Buchungen
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="px-4 py-2 font-medium">Ziffer</th>
                <th scope="col" className="px-4 py-2 font-medium">Bezeichnung</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Umsatz</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Steuer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {m.report.ziffern.map((row) => {
                const total = MWST_TOTAL_ZIFFERN.has(row.ziffer);
                const empty = isEmptyZiffer(row);
                // Leere Ziffern nur gedämpft beschriften — Text mit opacity fällt
                // unter die Kontrastschwelle (B-19).
                return (
                  <tr key={row.ziffer} className={cn(total && "bg-accent/40")}>
                    <td className={cn("px-4 py-2 font-mono text-xs", total && "font-semibold")}>{row.ziffer}</td>
                    <td
                      className={cn(
                        "px-4 py-2",
                        total && "font-semibold",
                        empty && !total ? "text-muted-foreground" : "text-foreground",
                      )}
                    >
                      {row.label}
                    </td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                      {row.umsatz == null ? "" : formatCHF(row.umsatz)}
                    </td>
                    <td
                      className={cn(
                        "px-4 py-2 text-right font-mono tabular-nums",
                        total ? "font-semibold text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {row.steuer == null ? "" : formatCHF(row.steuer)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="secondary"
          icon={m.copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          onClick={m.copy}
        >
          {m.copied ? "Kopiert" : "Für ePortal kopieren"}
        </Button>
        <Button size="sm" variant="ghost" icon={<Download className="h-3.5 w-3.5" />} onClick={m.download}>
          Blatt herunterladen
        </Button>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Receipt className="h-3.5 w-3.5" aria-hidden="true" />
          Entwurf aus den Buchungen — Ziffern ohne Buchungsgrundlage stehen auf 0.00 und sind selber zu prüfen.
        </p>
      </div>

      <ExportChecklist checks={m.report.checks} />
    </div>
  );
}
