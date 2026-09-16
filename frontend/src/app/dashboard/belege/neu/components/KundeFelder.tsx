import { SettingsInput } from "@/app/dashboard/settings/components/SettingsPrimitives";
import type { KundeForm } from "../types";

export function KundeFelder({ kunde, onChange }: {
  kunde: KundeForm;
  onChange: (field: keyof KundeForm, value: string) => void;
}) {
  return (
    <section aria-labelledby="kunde-titel" className="rounded-xl border border-border bg-card p-6">
      <h2 id="kunde-titel" className="text-base font-semibold text-foreground">Kunde</h2>
      <p className="mt-0.5 mb-4 text-sm text-muted-foreground">
        Name und Adresse stehen auf der Rechnung und im Zahlteil.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-6">
        <div className="sm:col-span-6">
          <label htmlFor="kunde-name" className="mb-1 block text-sm font-medium text-foreground">Name</label>
          <input
            id="kunde-name"
            value={kunde.name}
            onChange={(e) => onChange("name", e.target.value)}
            placeholder="Muster AG"
            className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="sm:col-span-4">
          <span className="mb-1 block text-sm font-medium text-foreground">Strasse</span>
          <SettingsInput label="Strasse" value={kunde.strasse} onChange={(v) => onChange("strasse", v)} placeholder="Seestrasse" />
        </div>
        <div className="sm:col-span-2">
          <span className="mb-1 block text-sm font-medium text-foreground">Nr.</span>
          <SettingsInput label="Hausnummer" value={kunde.hausnummer} onChange={(v) => onChange("hausnummer", v)} placeholder="12" />
        </div>
        <div className="sm:col-span-2">
          <span className="mb-1 block text-sm font-medium text-foreground">PLZ</span>
          <SettingsInput label="PLZ" value={kunde.plz} onChange={(v) => onChange("plz", v)} placeholder="6003" />
        </div>
        <div className="sm:col-span-4">
          <span className="mb-1 block text-sm font-medium text-foreground">Ort</span>
          <SettingsInput label="Ort" value={kunde.ort} onChange={(v) => onChange("ort", v)} placeholder="Luzern" />
        </div>
        <div className="sm:col-span-6">
          <span className="mb-1 block text-sm font-medium text-foreground">E-Mail (für Mahnungen)</span>
          <SettingsInput label="E-Mail des Kunden" type="email" value={kunde.email} onChange={(v) => onChange("email", v)} placeholder="rechnung@muster.ch" />
        </div>
      </div>
    </section>
  );
}
