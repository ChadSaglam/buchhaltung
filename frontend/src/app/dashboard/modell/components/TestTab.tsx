import { Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { accuracyTextClass } from "../helpers";
import type { ClassifyResult } from "../types";

interface TestTabProps {
  testInput: string;
  setTestInput: (value: string) => void;
  testResult: ClassifyResult | null;
  testLoading: boolean;
  handleTest: () => void;
}

export function TestTab({ testInput, setTestInput, testResult, testLoading, handleTest }: TestTabProps) {
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Geben Sie eine Beschreibung ein und sehen Sie, wie das Modell klassifiziert.
      </p>
      <div className="flex gap-3">
        <input
          type="text"
          aria-label="Beschreibung zum Testen"
          value={testInput}
          onChange={(e) => setTestInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleTest()}
          placeholder="z.B. Migros Zürich Lebensmittel"
          className="flex-1 px-4 py-2.5 border border-input rounded-xl text-sm text-foreground bg-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-ring transition-all"
        />
        <Button
          variant="primary"
          onClick={handleTest}
          disabled={testLoading || !testInput.trim()}
          loading={testLoading}
          icon={<Search className="w-4 h-4" />}
        >
          Testen
        </Button>
      </div>

      {testResult && (
        <div className="space-y-4 animate-fade-in">
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl bg-muted p-4">
              <div className="text-[11px] font-semibold text-muted-foreground uppercase mb-1">Quelle</div>
              <div className="text-base font-bold text-foreground">{testResult.source}</div>
            </div>
            <div className="rounded-xl bg-muted p-4">
              <div className="text-[11px] font-semibold text-muted-foreground uppercase mb-1">KtSoll</div>
              <div className="text-base font-bold text-foreground">{testResult.kt_soll}</div>
              <div className="text-xs text-muted-foreground">{testResult.kt_soll_name}</div>
            </div>
            <div className="rounded-xl bg-muted p-4">
              <div className="text-[11px] font-semibold text-muted-foreground uppercase mb-1">Konfidenz</div>
              <div className={cn("text-base font-bold tabular-nums", accuracyTextClass(testResult.confidence))}>
                {(testResult.confidence * 100).toFixed(0)}%
              </div>
            </div>
          </div>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <span><strong className="text-foreground">KtHaben:</strong> {testResult.kt_haben} ({testResult.kt_haben_name})</span>
            {testResult.mwst_code && (
              <span><strong className="text-foreground">MwSt:</strong> {testResult.mwst_code} / {testResult.mwst_pct}%</span>
            )}
          </div>

          {testResult.top_predictions && testResult.top_predictions.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-3">Top 5 ML-Vorhersagen</h4>
              <div className="space-y-2">
                {testResult.top_predictions.map((pred) => (
                  <div key={pred.klass} className="flex items-center gap-3">
                    <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono w-14 text-center text-foreground">
                      {pred.klass}
                    </code>
                    <span className="text-sm text-muted-foreground w-40 truncate">{pred.name}</span>
                    <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                      <div
                        className="h-full bg-brand-500 rounded-full transition-all"
                        style={{ width: `${pred.probability * 100}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold tabular-nums w-12 text-right text-foreground">
                      {(pred.probability * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
