"use client";

import { useState } from "react";
import { Zap, ChevronDown, ChevronUp, ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

function PipelineStep({ num, label, desc, tone }: { num: number; label: string; desc: string; tone: "success" | "brand" | "warning" }) {
  const styles = {
    success: "bg-success/10 text-success",
    brand: "bg-brand-500/12 text-brand-600 dark:text-brand-300",
    warning: "bg-warning/12 text-warning",
  }[tone];
  return (
    <div className={cn("flex-1 rounded-xl px-4 py-3", styles)}>
      <div className="text-[11px] font-bold opacity-60">Stufe {num}</div>
      <div className="font-semibold text-sm mt-0.5">{label}</div>
      <div className="text-xs opacity-70 mt-0.5">{desc}</div>
    </div>
  );
}

export function PipelineCard() {
  const [showHowItWorks, setShowHowItWorks] = useState(false);

  return (
    <Card>
      <CardContent className="pt-5">
        <button
          onClick={() => setShowHowItWorks(!showHowItWorks)}
          className="w-full flex items-center justify-between"
        >
          <h3 className="font-semibold text-foreground flex items-center gap-2">
            <Zap className="w-4 h-4 text-warning" />
            Klassifizierungs-Pipeline
          </h3>
          {showHowItWorks ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
        </button>

        <div className="flex items-center gap-2 mt-4">
          <PipelineStep num={1} label="Gedächtnis" desc="Exakte Treffer" tone="success" />
          <ArrowRight className="w-4 h-4 text-muted-foreground/40 shrink-0" />
          <PipelineStep num={2} label="ML-Modell" desc="TF-IDF + LogReg" tone="brand" />
          <ArrowRight className="w-4 h-4 text-muted-foreground/40 shrink-0" />
          <PipelineStep num={3} label="Regeln" desc="Keyword-Fallback" tone="warning" />
        </div>

        {showHowItWorks && (
          <div className="mt-5 p-4 rounded-xl bg-muted text-sm text-foreground space-y-2 animate-fade-in">
            <p><strong>So lernt das System:</strong></p>
            <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
              <li>Sie scannen eine Rechnung → Vision liest Lieferant, Datum, Betrag</li>
              <li>ML klassifiziert → schlägt Konten vor</li>
              <li>Sie bestätigen oder korrigieren</li>
              <li>System speichert im Gedächtnis → beim nächsten Mal sofort korrekt</li>
            </ol>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
