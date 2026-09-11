import { Zap } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { t } from "@/lib/i18n";

interface Props {
  correctionCount: number;
  training: boolean;
  trainResult: string | null;
  onTrain: () => void;
}

export function TrainingCard({ correctionCount, training, trainResult, onTrain }: Props) {
  const failed = trainResult?.startsWith("Fehler");
  return (
    <Card>
      <CardHeader>
        <CardTitle>Modell trainieren</CardTitle>
        <CardDescription>
          {correctionCount
            ? `${correctionCount} Korrekturen verfügbar zum Trainieren.`
            : "Noch keine Korrekturen vorhanden."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button
          variant="success"
          onClick={onTrain}
          disabled={training}
          loading={training}
          icon={<Zap className="h-4 w-4" aria-hidden="true" />}
        >
          {training ? t("kontenplan.training") : t("modell.train_button")}
        </Button>
        {trainResult && (
          <div
            role={failed ? "alert" : "status"}
            className={`mt-4 p-3 rounded-lg text-sm ${
              failed
                ? "bg-destructive/10 text-destructive border border-destructive/20"
                : "bg-success/10 text-success border border-success/20"
            }`}
          >
            {trainResult}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
