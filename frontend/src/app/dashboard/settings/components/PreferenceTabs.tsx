import { SettingsField, SettingsToggle } from "./SettingsPrimitives";

export function ReviewTab({ threshold, setThreshold }: { threshold: number; setThreshold: (v: number) => void }) {
  return (
    <div>
      <h2 className="text-base font-semibold text-foreground mb-1">Überprüfung</h2>
      <p className="text-sm text-muted-foreground mb-6">Schwelle für die Überprüfungs-Warteschlange festlegen</p>
      <SettingsField
        label="Konfidenz-Schwelle"
        description="Vorhersagen unter diesem Wert landen in der Überprüfungs-Warteschlange"
      >
        <div className="flex items-center gap-4">
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="flex-1 accent-brand-600"
            aria-label="Konfidenz-Schwelle"
          />
          <span className="w-16 text-right font-mono text-sm text-foreground tabular-nums">
            {Math.round(threshold * 100)}%
          </span>
        </div>
      </SettingsField>
    </div>
  );
}

export function NotificationsTab({ emailNotifs, setEmailNotifs, exportNotifs, setExportNotifs }: {
  emailNotifs: boolean;
  setEmailNotifs: (v: boolean) => void;
  exportNotifs: boolean;
  setExportNotifs: (v: boolean) => void;
}) {
  return (
    <div>
      <h2 className="text-base font-semibold text-foreground mb-1">Benachrichtigungen</h2>
      <p className="text-sm text-muted-foreground mb-6">E-Mail- und App-Benachrichtigungen</p>
      <SettingsField label="E-Mail-Benachrichtigungen">
        <div className="space-y-4">
          <SettingsToggle checked={emailNotifs} onChange={setEmailNotifs} label="Tägliche Zusammenfassung" />
          <SettingsToggle checked={exportNotifs} onChange={setExportNotifs} label="Export-Bestätigung per E-Mail" />
        </div>
      </SettingsField>
    </div>
  );
}
