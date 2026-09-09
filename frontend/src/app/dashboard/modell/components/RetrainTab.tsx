import { CheckCircle, Info, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { ModelInfo } from "../types";

interface RetrainTabProps {
  info: ModelInfo | null;
  training: boolean;
  handleTrain: () => void;
}

export function RetrainTab({ info, training, handleTrain }: RetrainTabProps) {
  return (
    <div className="space-y-4">
      {(info?.correction_count ?? 0) > 0 ? (
        <>
          <div className="flex items-center gap-3 p-4 rounded-xl bg-info/10 border border-info/25 text-info">
            <Info className="w-5 h-5 shrink-0" />
            <span className="text-sm">
              <strong>{info?.correction_count} Korrekturen</strong> seit letztem Training verfügbar.
              Neu trainieren verbessert die Genauigkeit.
            </span>
          </div>
          <Button
            variant="primary"
            onClick={handleTrain}
            disabled={training}
            loading={training}
            icon={<RotateCcw className="w-4 h-4" />}
          >
            Jetzt neu trainieren
          </Button>
        </>
      ) : (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-success/10 border border-success/25 text-success">
          <CheckCircle className="w-5 h-5 shrink-0" />
          <span className="text-sm">Modell ist aktuell — keine neuen Korrekturen vorhanden.</span>
        </div>
      )}
      <p className="text-xs text-muted-foreground pt-2">
        Je mehr Rechnungen Sie scannen und bestätigen, desto besser wird das Modell.
      </p>
    </div>
  );
}
