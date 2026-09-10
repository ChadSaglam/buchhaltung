import { Brain, Cpu, Shield, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { DangerAction, ModelInfo } from "../types";

interface DangerZoneProps {
  info: ModelInfo | null;
  dangerConfirm: string | null;
  setDangerConfirm: (key: string | null) => void;
  handleDangerAction: (action: DangerAction) => void;
}

export function DangerZone({ info, dangerConfirm, setDangerConfirm, handleDangerAction }: DangerZoneProps) {
  return (
    <div className="rounded-xl border border-destructive/25 bg-card p-6 shadow-sm">
      <h3 className="font-semibold text-destructive flex items-center gap-2 mb-1">
        <Shield className="w-4 h-4" />
        Gefahrenzone
      </h3>
      <p className="text-xs text-muted-foreground mb-4">Diese Aktionen können nicht rückgängig gemacht werden — sichern Sie zuerst Ihr Modell.</p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { key: "memory", label: "Gedächtnis leeren", icon: Brain, count: info?.memory_count },
          { key: "corrections", label: "Korrekturen leeren", icon: TrendingUp, count: info?.correction_count },
          { key: "model", label: "ML-Modell löschen", icon: Cpu, count: info?.has_model ? 1 : 0 },
        ].map(({ key, label, icon: Icon, count }) => (
          <div key={key}>
            {dangerConfirm === key ? (
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  size="sm"
                  className="flex-1"
                  onClick={() => handleDangerAction(key as DangerAction)}
                >
                  Bestätigen
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDangerConfirm(null)}
                >
                  Abbrechen
                </Button>
              </div>
            ) : (
              <Button
                variant="danger"
                size="sm"
                className="w-full"
                onClick={() => setDangerConfirm(key)}
                disabled={!count}
                icon={<Icon className="w-4 h-4" />}
              >
                {label}
              </Button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
