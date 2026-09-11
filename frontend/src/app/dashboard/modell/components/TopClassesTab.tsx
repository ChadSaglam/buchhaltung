import { Database } from "lucide-react";
import type { TrainingData } from "../types";

export function TopClassesTab({ topClasses }: { topClasses: TrainingData[] }) {
  return (
    <div>
      <p className="text-sm text-muted-foreground mb-4">Häufigste Kontoklassen im Trainingsset</p>
      {topClasses.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm" aria-label="Häufigste Konten">
            <thead>
              <tr className="bg-muted text-left">
                <th className="px-4 py-2.5 font-semibold text-muted-foreground">KontoSoll</th>
                <th className="px-4 py-2.5 font-semibold text-muted-foreground">Bezeichnung</th>
                <th className="px-4 py-2.5 font-semibold text-muted-foreground text-right">Anzahl</th>
                <th className="px-4 py-2.5 font-semibold text-muted-foreground w-40">Verteilung</th>
              </tr>
            </thead>
            <tbody>
              {topClasses.map((cls) => {
                const maxCount = topClasses[0]?.anzahl ?? 1;
                return (
                  <tr key={cls.konto_soll} className="border-t border-border hover:bg-accent transition-colors">
                    <td className="px-4 py-2.5 font-mono font-medium text-foreground">{cls.konto_soll}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{cls.bezeichnung}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-medium text-foreground">{cls.anzahl}</td>
                    <td className="px-4 py-2.5">
                      <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full bg-brand-500 rounded-full"
                          style={{ width: `${(cls.anzahl / maxCount) * 100}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <Database className="w-8 h-8 mb-2 opacity-40" />
          <p className="text-sm">Keine Trainingsdaten vorhanden</p>
        </div>
      )}
    </div>
  );
}
