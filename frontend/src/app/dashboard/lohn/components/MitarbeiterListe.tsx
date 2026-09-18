"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";
import { formatCHF, formatDate } from "@/lib/format";
import { SettingsField, SettingsInput } from "../../settings/components/SettingsPrimitives";
import { anzeigeName, betragWert, satzWert, type Mitarbeiter } from "@/lib/lohn";

const LEER = {
  vorname: "",
  name: "",
  ahv_nummer: "",
  eintritt: "",
  lohnart: "monat" as "monat" | "stunde",
  monatslohn: "",
  stundenlohn: "",
  bvg_an_monat: "",
  bvg_ag_monat: "",
  kinderzulagen_monat: "",
  quellensteuer_satz: "",
};

/**
 * The employees payroll knows about (B-72).
 *
 * BVG is entered as a *franc amount*, not a rate, because that is how the
 * pension fund sends it: age, insured salary and the plan decide it, and a
 * number this app derived would disagree with the one that gets paid.
 */
export function MitarbeiterListe({
  liste,
  onCreate,
}: {
  liste: Mitarbeiter[];
  onCreate: (werte: Record<string, unknown>) => Promise<boolean>;
}) {
  const [offen, setOffen] = useState(false);
  const [entwurf, setEntwurf] = useState(LEER);
  const [saving, setSaving] = useState(false);

  const setFeld = (feld: keyof typeof LEER, value: string) =>
    setEntwurf((current) => ({ ...current, [feld]: value }));

  const stuendlich = entwurf.lohnart === "stunde";

  const anlegen = async () => {
    setSaving(true);
    try {
      const ok = await onCreate({
        vorname: entwurf.vorname,
        name: entwurf.name,
        ahv_nummer: entwurf.ahv_nummer,
        eintritt: entwurf.eintritt || null,
        lohnart: entwurf.lohnart,
        // B-100: the two are exclusive, so only the one in use is sent. Leaving a
        // stale Monatslohn on an hourly employee would show a salary nobody is paid.
        monatslohn: stuendlich ? 0 : (betragWert(entwurf.monatslohn) ?? 0),
        stundenlohn: stuendlich ? (betragWert(entwurf.stundenlohn) ?? 0) : 0,
        bvg_an_monat: betragWert(entwurf.bvg_an_monat),
        bvg_ag_monat: betragWert(entwurf.bvg_ag_monat),
        kinderzulagen_monat: betragWert(entwurf.kinderzulagen_monat) ?? 0,
        quellensteuer: Boolean(satzWert(entwurf.quellensteuer_satz)),
        quellensteuer_satz: satzWert(entwurf.quellensteuer_satz),
      });
      if (ok) {
        setEntwurf(LEER);
        setOffen(false);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <section aria-labelledby="mitarbeiter-titel" className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 id="mitarbeiter-titel" className="text-base font-semibold text-foreground">
          Mitarbeitende
        </h2>
        <Button
          variant="secondary"
          onClick={() => setOffen((v) => !v)}
          icon={<UserPlus className="h-4 w-4" />}
          aria-expanded={offen}
        >
          {offen ? "Abbrechen" : "Neu"}
        </Button>
      </div>

      {offen && (
        <div className="mb-6 rounded-lg border border-border bg-surface p-4">
          <SettingsField label="Name">
            <div className="flex gap-2">
              <SettingsInput label="Vorname" value={entwurf.vorname} onChange={(v) => setFeld("vorname", v)} placeholder="Vorname" />
              <SettingsInput label="Nachname" value={entwurf.name} onChange={(v) => setFeld("name", v)} placeholder="Nachname" />
            </div>
          </SettingsField>
          <SettingsField label="AHV-Nummer" description="756.xxxx.xxxx.xx">
            <SettingsInput label="AHV-Nummer" value={entwurf.ahv_nummer} onChange={(v) => setFeld("ahv_nummer", v)} />
          </SettingsField>
          <SettingsField label="Eintritt">
            <SettingsInput label="Eintrittsdatum" type="date" value={entwurf.eintritt} onChange={(v) => setFeld("eintritt", v)} />
          </SettingsField>
          {/* B-100: how this person is paid decides which field below means anything. */}
          <SettingsField label="Bezahlt nach" description="Fester Monatslohn oder Stundenlohn. Alles Weitere — AHV, ALV, UVG, Zulagen — ist in beiden Fällen gleich.">
            <div className="flex gap-4">
              {(["monat", "stunde"] as const).map((art) => (
                <label key={art} className="flex items-center gap-2 text-sm text-foreground">
                  <input
                    type="radio"
                    name="lohnart"
                    value={art}
                    checked={entwurf.lohnart === art}
                    onChange={() => setFeld("lohnart", art)}
                  />
                  {art === "monat" ? "Monat" : "Stunde"}
                </label>
              ))}
            </div>
          </SettingsField>
          {stuendlich ? (
            <SettingsField
              label="Stundenlohn (CHF)"
              description="Brutto pro Stunde. Die Stunden selbst werden pro Abrechnung erfasst — ein Teilmonat steckt schon in den Stunden und wird nicht zusätzlich gekürzt."
            >
              <SettingsInput label="Stundenlohn" value={entwurf.stundenlohn} onChange={(v) => setFeld("stundenlohn", v)} placeholder="32.50" />
            </SettingsField>
          ) : (
            <SettingsField label="Monatslohn (CHF)" description="Brutto für einen ganzen Monat">
              <SettingsInput label="Monatslohn" value={entwurf.monatslohn} onChange={(v) => setFeld("monatslohn", v)} placeholder="6000" />
            </SettingsField>
          )}
          <SettingsField
            label="BVG pro Monat (CHF)"
            description="Aus der Abrechnung der Pensionskasse — Arbeitnehmer / Arbeitgeber"
          >
            <div className="flex gap-2">
              <SettingsInput label="BVG Arbeitnehmer" value={entwurf.bvg_an_monat} onChange={(v) => setFeld("bvg_an_monat", v)} placeholder="AN" />
              <SettingsInput label="BVG Arbeitgeber" value={entwurf.bvg_ag_monat} onChange={(v) => setFeld("bvg_ag_monat", v)} placeholder="AG" />
            </div>
          </SettingsField>
          <SettingsField
            label="Kinderzulagen pro Monat (CHF)"
            description="Aus der Verfügung der Ausgleichskasse. Werden mit dem Lohn ausbezahlt und sind nicht AHV-pflichtig — keine Prozentzeile rechnet darauf."
          >
            <SettingsInput label="Kinderzulagen" value={entwurf.kinderzulagen_monat} onChange={(v) => setFeld("kinderzulagen_monat", v)} placeholder="0" />
          </SettingsField>
          <SettingsField
            label="Quellensteuer (%)"
            description="Satz aus dem kantonalen Tarif; leer lassen, wenn nicht quellenbesteuert"
          >
            <SettingsInput label="Quellensteuersatz" value={entwurf.quellensteuer_satz} onChange={(v) => setFeld("quellensteuer_satz", v)} />
          </SettingsField>
          <div className="mt-4 flex justify-end">
            <Button
              onClick={anlegen}
              loading={saving}
              disabled={saving || !entwurf.name.trim() || (stuendlich && !betragWert(entwurf.stundenlohn))}
            >
              Anlegen
            </Button>
          </div>
        </div>
      )}

      {liste.length === 0 ? (
        <EmptyState
          as="h3"
          title="Noch niemand angelegt"
          description="Lohn braucht mindestens eine Person — im Monats- oder im Stundenlohn."
        />
      ) : (
        <ul className="divide-y divide-border">
          {liste.map((person) => (
            <li key={person.id} className="flex items-center justify-between gap-4 py-3">
              <div>
                <p className="text-sm font-medium text-foreground">{anzeigeName(person)}</p>
                <p className="text-xs text-muted-foreground">
                  {person.eintritt ? `seit ${formatDate(person.eintritt)}` : "ohne Eintrittsdatum"}
                  {person.austritt ? ` · ausgetreten ${formatDate(person.austritt)}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm tabular-nums text-foreground">
                  {person.lohnart === "stunde" ? `${formatCHF(person.stundenlohn)} / h` : formatCHF(person.monatslohn)}
                </span>
                {person.austritt && <Badge tone="neutral">ausgetreten</Badge>}
                {person.quellensteuer && <Badge tone="info">Quellensteuer</Badge>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
