import { CheckCircle, AlertTriangle, XCircle } from "lucide-react";

export function SystemStatusBadge({ hasModel, hasVision }: { hasModel: boolean; hasVision: boolean }) {
  if (hasModel && hasVision) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-success/10 border border-success/25 text-success text-sm font-medium">
        <CheckCircle className="w-4 h-4" />
        Buchhaltung Modell vollständig — Vision + ML aktiv
      </div>
    );
  }
  if (hasModel || hasVision) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-warning/10 border border-warning/25 text-warning text-sm font-medium">
        <AlertTriangle className="w-4 h-4" />
        Teilweise aktiv — {hasModel ? "ML bereit, Vision fehlt" : "Vision bereit, ML fehlt"}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-destructive/10 border border-destructive/25 text-destructive text-sm font-medium">
      <XCircle className="w-4 h-4" />
      Nicht konfiguriert — Modell trainieren & Vision installieren
    </div>
  );
}
