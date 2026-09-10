import { Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import { accuracyBarClass, accuracyTextClass, formatDate, isOverfit } from "../helpers";
import type { ModelInfo } from "../types";

export function AccuracyCard({ info, acc }: { info: ModelInfo; acc: number }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-foreground">Modell-Genauigkeit</span>
            {isOverfit(info.train_accuracy, acc) && (
              <Badge tone="warning" dot>Overfit-Warnung</Badge>
            )}
          </div>
          <span className={cn("text-xl font-extrabold tabular-nums", accuracyTextClass(acc))}>
            {(acc * 100).toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all duration-1000 ease-out", accuracyBarClass(acc))}
            style={{ width: `${Math.min(acc * 100, 100)}%` }}
          />
        </div>
        <div className="flex justify-between mt-3 text-xs text-muted-foreground">
          <span className="tabular-nums">{info.total_samples} Buchungen · {info.classes} Klassen</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatDate(info.trained_at)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
