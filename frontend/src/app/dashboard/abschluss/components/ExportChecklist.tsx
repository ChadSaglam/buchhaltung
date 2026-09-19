import { AlertTriangle, Check, X } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import { checkCountLabel, checkTone, sortChecks } from "../helpers";
import type { ExportCheck } from "../types";

const ICON = {
  success: Check,
  danger: X,
  warning: AlertTriangle,
} as const;

const TONE = {
  success: "text-success bg-success/12",
  danger: "text-destructive bg-destructive/12",
  warning: "text-warning bg-warning/15",
} as const;

export function ExportChecklist({ checks }: { checks: ExportCheck[] }) {
  return (
    <Card>
      <ul className="divide-y divide-border">
        {sortChecks(checks).map((check) => {
          const tone = checkTone(check);
          const Icon = ICON[tone];
          const count = checkCountLabel(check);
          return (
            <li key={check.code} className="flex items-start gap-3 px-4 py-3">
              <span className={cn("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full", TONE[tone])}>
                <Icon className="h-4 w-4" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">{check.label}</p>
                {tone !== "success" && <p className="mt-0.5 text-xs text-muted-foreground">{check.detail}</p>}
              </div>
              {count && (
                <span
                  className={cn(
                    "shrink-0 rounded-md px-2 py-0.5 text-xs font-medium tabular-nums",
                    tone === "danger" ? "bg-destructive/12 text-destructive" : "bg-warning/15 text-warning",
                  )}
                >
                  {count}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
