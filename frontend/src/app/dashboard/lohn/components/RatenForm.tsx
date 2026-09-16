"use client";

import { useEffect, useState } from "react";
import { Check, Save } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SettingsField, SettingsInput } from "../../settings/components/SettingsPrimitives";
import { FREIWILLIGE_SAETZE, PFLICHTSAETZE, satzWert, type LohnSettings } from "@/lib/lohn";

const ALLE = [...PFLICHTSAETZE.map((s) => s.feld), ...FREIWILLIGE_SAETZE.map((s) => s.feld)] as const;
type Feld = (typeof ALLE)[number];

/**
 * The rates that are not federal (B-72).
 *
 * The two groups are visually separate because the difference is not cosmetic:
 * an empty compulsory field blocks every payslip, while an empty voluntary one
 * means "we are not insured for this" and is a perfectly good answer.
 */
export function RatenForm({
  settings,
  onSave,
}: {
  settings: LohnSettings | undefined;
  onSave: (werte: Record<string, number | null>) => Promise<void>;
}) {
  const [entwurf, setEntwurf] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!settings) return;
    const werte = settings as unknown as Record<string, number | null>;
    setEntwurf(Object.fromEntries(ALLE.map((f) => [f, werte[f] == null ? "" : String(werte[f])])));
  }, [settings]);

  const setFeld = (feld: Feld, value: string) => {
    setSaved(false);
    setEntwurf((current) => ({ ...current, [feld]: value }));
  };

  const speichern = async () => {
    setSaving(true);
    try {
      await onSave(Object.fromEntries(ALLE.map((f) => [f, satzWert(entwurf[f] ?? "")])));
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section aria-labelledby="saetze-titel" className="rounded-xl border border-border bg-card p-6">
      <div className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h2 id="saetze-titel" className="text-base font-semibold text-foreground">
            Sätze der Versicherungen
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            AHV/IV/EO und ALV sind gesetzlich und stehen fest. Alles hier steht im Vertrag mit der
            Versicherung oder wird vom Kanton bestimmt — darum kann es niemand für Sie raten.
          </p>
        </div>
        <Button
          variant={saved ? "success" : "primary"}
          onClick={speichern}
          loading={saving}
          disabled={saving}
          icon={saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
        >
          {saved ? "Gespeichert" : "Speichern"}
        </Button>
      </div>

      {PFLICHTSAETZE.map((satz) => (
        <SettingsField key={satz.feld} label={`${satz.label} (%)`} description={satz.hinweis}>
          <SettingsInput
            label={`${satz.label} in Prozent`}
            value={entwurf[satz.feld] ?? ""}
            onChange={(v) => setFeld(satz.feld, v)}
            placeholder="z. B. 1.6"
          />
        </SettingsField>
      ))}

      <h3 className="mt-6 text-sm font-medium text-foreground">Freiwillige Versicherungen</h3>
      <p className="mb-1 text-xs text-muted-foreground">
        Leer lassen heisst: nicht versichert. Dann erscheint die Zeile gar nicht auf der Abrechnung.
      </p>
      {FREIWILLIGE_SAETZE.map((satz) => (
        <SettingsField key={satz.feld} label={`${satz.label} (%)`}>
          <SettingsInput
            label={`${satz.label} in Prozent`}
            value={entwurf[satz.feld] ?? ""}
            onChange={(v) => setFeld(satz.feld, v)}
            placeholder="leer = nicht versichert"
          />
        </SettingsField>
      ))}
    </section>
  );
}
