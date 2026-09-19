import { motion } from "motion/react";
import { ArrowRight, Check, FileText, Landmark, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatCHF, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { TIER_LABEL, TIER_TONE, documentTotal } from "../helpers";
import type { AbgleichItem } from "../types";

interface Props {
  item: AbgleichItem;
  active: boolean;
  busy: boolean;
  onSelect: () => void;
  onConfirm: () => void;
  onReject: () => void;
}

export function ProposalCard({ item, active, busy, onSelect, onConfirm, onReject }: Props) {
  const tx = item.transaction;
  const total = documentTotal(item);
  return (
    <motion.div
      role="option"
      aria-selected={active}
      onClick={onSelect}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "rounded-xl border bg-card p-4 transition-colors",
        active ? "border-brand-500 ring-2 ring-brand-500/30" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={TIER_TONE[item.tier] ?? "neutral"} dot>
          {TIER_LABEL[item.tier] ?? item.tier}
        </Badge>
        <p className="text-sm text-muted-foreground">{item.reason}</p>
      </div>

      <div className="mt-3 grid grid-cols-1 items-center gap-3 md:grid-cols-[1fr_auto_1fr]">
        {/* the bank line */}
        <div className="flex items-start gap-2.5 rounded-lg bg-muted/60 p-3">
          <Landmark className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{tx.description || "Bankzeile"}</p>
            <p className="text-xs text-muted-foreground">
              {formatDate(tx.value_date)} · <span className="font-mono tabular-nums">{formatCHF(tx.amount, tx.currency)}</span>
            </p>
          </div>
        </div>

        <ArrowRight className="mx-auto hidden h-4 w-4 text-muted-foreground md:block" aria-hidden="true" />

        {/* the invoice(s) it settles */}
        <div className="space-y-2">
          {item.documents.map((d) => (
            <div key={d.match_id} className="flex items-start gap-2.5 rounded-lg border border-border p-3">
              <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {d.document.vendor || d.document.filename}
                </p>
                <p className="text-xs text-muted-foreground">
                  {d.document.invoice_no ? `${d.document.invoice_no} · ` : ""}
                  {formatDate(d.document.invoice_date)} ·{" "}
                  <span className="font-mono tabular-nums">{formatCHF(d.amount)}</span>
                  {d.document.kt_soll ? ` · ${d.document.kt_soll}/${d.document.kt_haben}` : ""}
                </p>
              </div>
            </div>
          ))}
          {item.is_split && (
            <p className="text-right text-xs text-muted-foreground">
              Summe <span className="font-mono tabular-nums">{formatCHF(total)}</span>
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <Button
          variant="success"
          size="sm"
          onClick={onConfirm}
          disabled={busy}
          loading={busy}
          icon={<Check className="h-4 w-4" aria-hidden="true" />}
          aria-label={`Vorschlag für ${tx.description || "Bankzeile"} bestätigen`}
        >
          Stimmt
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onReject}
          disabled={busy}
          icon={<X className="h-4 w-4" aria-hidden="true" />}
          aria-label={`Vorschlag für ${tx.description || "Bankzeile"} ablehnen`}
        >
          Passt nicht
        </Button>
      </div>
    </motion.div>
  );
}
