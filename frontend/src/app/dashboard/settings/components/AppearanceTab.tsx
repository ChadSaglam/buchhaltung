import { Check, Languages } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import { useThemeStore, ACCENTS, type Accent } from "@/lib/theme-store";
import { THEME_OPTIONS } from "../helpers";
import { SettingsField } from "./SettingsPrimitives";

export function AppearanceTab() {
  const { theme, accent, setTheme, setAccent } = useThemeStore();

  return (
    <div>
      <h2 className="text-base font-semibold text-foreground mb-1">Darstellung</h2>
      <p className="text-sm text-muted-foreground mb-6">Theme und Akzentfarbe anpassen — Änderungen werden sofort übernommen</p>
      <SettingsField label="Theme" description="Hell, Dunkel oder automatisch nach System">
        <div className="grid grid-cols-3 gap-3">
          {THEME_OPTIONS.map((opt) => {
            const active = theme === opt.id;
            return (
              <button
                key={opt.id}
                onClick={() => setTheme(opt.id)}
                aria-pressed={active}
                className={cn(
                  "group relative flex flex-col items-center gap-2 rounded-xl border-2 p-3 transition-all",
                  active
                    ? "border-primary bg-brand-500/8"
                    : "border-border hover:border-border-strong"
                )}
              >
                <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg", active ? "bg-brand-500/15 text-brand-600 dark:text-brand-300" : "bg-muted text-muted-foreground")}>
                  <opt.icon className="h-[18px] w-[18px]" />
                </span>
                <span className={cn("text-xs font-medium", active ? "text-foreground" : "text-muted-foreground")}>{opt.label}</span>
                {active && (
                  <span className="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <Check className="h-2.5 w-2.5" />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </SettingsField>
      <SettingsField label="Akzentfarbe" description="Bestimmt Buttons, Links und Hervorhebungen">
        <div className="flex flex-wrap gap-3">
          {(Object.keys(ACCENTS) as Accent[]).map((key) => {
            const a = ACCENTS[key];
            const active = accent === key;
            return (
              <button
                key={key}
                onClick={() => setAccent(key)}
                aria-label={a.label}
                title={a.label}
                className={cn(
                  "relative flex h-10 w-10 items-center justify-center rounded-full transition-transform hover:scale-105",
                  active && "ring-2 ring-offset-2 ring-offset-card"
                )}
                style={{ backgroundColor: a.swatch, ...(active ? { boxShadow: `0 0 0 2px ${a.swatch}` } : {}) }}
              >
                {active && <Check className="h-4 w-4 text-white" />}
              </button>
            );
          })}
        </div>
      </SettingsField>
      <SettingsField label="Sprache" description="Sprache der Benutzeroberfläche">
        <div className="flex flex-wrap items-center gap-3" aria-disabled="true">
          <div className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg border border-border bg-muted px-3 py-2 opacity-70">
            <Languages className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">Deutsch</span>
          </div>
          <Badge tone="info">Bald verfügbar</Badge>
          <p className="basis-full text-xs text-muted-foreground">
            Englisch und Französisch folgen in einer späteren Version. Die Umschaltung ist vorübergehend deaktiviert.
          </p>
        </div>
      </SettingsField>
    </div>
  );
}
