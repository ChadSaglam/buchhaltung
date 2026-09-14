import { useEffect, useRef } from "react";
import { motion } from "motion/react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { ReviewItem } from "../types";

interface Props {
  items: ReviewItem[];
  selected: number;
  onSelect: (idx: number) => void;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}

export function ReviewList({ items, selected, onSelect, onApprove, onReject }: Props) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    listRef.current?.children[selected]?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  return (
    <div ref={listRef} role="listbox" aria-label="Offene Überprüfungen" className="space-y-3">
      {items.map((item, idx) => (
        <motion.div
          key={item.id}
          role="option"
          aria-selected={idx === selected}
          onClick={() => onSelect(idx)}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, delay: Math.min(idx * 0.05, 0.3) }}
          className={cn(
            "flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border bg-card p-4 transition-colors",
            idx === selected ? "border-brand-500 ring-2 ring-brand-500/30" : "border-border",
          )}
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{item.beschreibung}</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span className="tabular-nums">Betrag: {item.betrag.toFixed(2)}</span>
              <span className="font-mono">
                {item.predicted_soll} / {item.predicted_haben}
                {item.predicted_mwst_code ? ` · ${item.predicted_mwst_code}` : ""}
              </span>
              <span>Quelle: {item.source}</span>
            </div>
          </div>

          <Badge tone={item.confidence < 0.5 ? "danger" : "warning"}>{Math.round(item.confidence * 100)}%</Badge>

          <div className="flex shrink-0 gap-2">
            <Button variant="success" size="sm" onClick={() => onApprove(item.id)} icon={<CheckCircle2 className="h-4 w-4" />}>
              Bestätigen
            </Button>
            <Button variant="outline" size="sm" onClick={() => onReject(item.id)} icon={<XCircle className="h-4 w-4" />}>
              Verwerfen
            </Button>
          </div>
        </motion.div>
      ))}
      <p className="text-xs text-muted-foreground">
        Tastatur: <kbd className="rounded border border-border px-1">j</kbd>/<kbd className="rounded border border-border px-1">k</kbd> wählen ·{" "}
        <kbd className="rounded border border-border px-1">a</kbd> bestätigen · <kbd className="rounded border border-border px-1">r</kbd> verwerfen
      </p>
    </div>
  );
}
