"use client";

import { Calculator, FileDown, Lock } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { API_URL } from "@/lib/api";
import { formatCHF } from "@/lib/format";
import { SettingsField, SettingsInput, SettingsToggle } from "../../settings/components/SettingsPrimitives";
import {
  MONATE,
  anteilSatz,
  anzeigeName,
  istAbgerechnet,
  nettoSatz,
  satzLabel,
  type Lohnlauf,
  type Mitarbeiter,
} from "@/lib/lohn";

interface Props {
  waehlbar: Mitarbeiter[];
  gewaehlt: number | null;
  setGewaehlt: (id: number | null) => void;
  jahr: number;
  monat: number;
  setJahr: (v: number) => void;
  setMonat: (v: number) => void;
  zulagen: string;
  setZulagen: (v: string) => void;
  dreizehnter: boolean;
  setDreizehnter: (v: boolean) => void;
  lauf: Lohnlauf | null;
  laufFehler: string;
  busy: boolean;
  bereit: boolean;
  vorschau: () => void;
  abrechnen: () => void;
}

/**
 * Preview, then issue (B-72).
 *
 * Both buttons post the same body to the same engine; the only difference is
 * whether a payslip and its bookings are written. Issuing is deliberately the
 * second click, because it is the one action in this app that cannot be undone.
 */
export function AbrechnungPanel(p: Props) {
  const jahre = [p.jahr - 1, p.jahr, p.jahr + 1];
  const abgerechnet = istAbgerechnet(p.lauf ?? undefined);

  return (
    <section aria-labelledby="abrechnen-titel" className="rounded-xl border border-border bg-card p-6">
      <h2 id="abrechnen-titel" className="mb-1 text-base font-semibold text-foreground">
        Lohn abrechnen
      </h2>
      <p className="mb-4 text-xs text-muted-foreground">
        Zuerst ansehen, dann abrechnen. Abgerechnet wird ein Monat nur einmal — eine Korrektur ist
        eine neue Abrechnung, keine Änderung an der alten.
      </p>

      <SettingsField label="Mitarbeiter">
        <select
          aria-label="Mitarbeiter"
          value={p.gewaehlt ?? ""}
          onChange={(e) => p.setGewaehlt(e.target.value ? Number(e.target.value) : null)}
          className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {p.waehlbar.length === 0 && <option value="">Niemand angestellt in diesem Monat</option>}
          {p.waehlbar.map((m) => (
            <option key={m.id} value={m.id}>
              {anzeigeName(m)}
            </option>
          ))}
        </select>
      </SettingsField>

      <SettingsField label="Periode">
        <div className="flex gap-2">
          <select
            aria-label="Monat"
            value={p.monat}
            onChange={(e) => p.setMonat(Number(e.target.value))}
            className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {MONATE.map((name, index) => (
              <option key={name} value={index + 1}>
                {name}
              </option>
            ))}
          </select>
          <select
            aria-label="Jahr"
            value={p.jahr}
            onChange={(e) => p.setJahr(Number(e.target.value))}
            className="w-32 rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {jahre.map((j) => (
              <option key={j} value={j}>
                {j}
              </option>
            ))}
          </select>
        </div>
      </SettingsField>

      <SettingsField label="Zulage, AHV-pflichtig (CHF)" description="Einmalig für diesen Monat — Gratifikation, Bonus. Kinderzulagen gehören nicht hierher: sie stehen beim Mitarbeiter und sind AHV-frei.">
        <SettingsInput label="Zulagen" value={p.zulagen} onChange={p.setZulagen} placeholder="0" />
      </SettingsField>

      <SettingsField label="13. Monatslohn" description="Wird anteilig nach Anstellungsdauer berechnet">
        <SettingsToggle label="Mit diesem Monat auszahlen" checked={p.dreizehnter} onChange={p.setDreizehnter} />
      </SettingsField>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          variant="secondary"
          onClick={p.vorschau}
          loading={p.busy}
          disabled={p.busy || p.gewaehlt == null}
          icon={<Calculator className="h-4 w-4" />}
        >
          Ansehen
        </Button>
        <Button
          onClick={p.abrechnen}
          loading={p.busy}
          disabled={p.busy || p.gewaehlt == null || !p.bereit || abgerechnet}
          icon={<Lock className="h-4 w-4" />}
        >
          Abrechnen und verbuchen
        </Button>
        {abgerechnet && p.lauf && (
          <a
            href={`${API_URL}/api/lohn/abrechnungen/${p.lauf.abrechnung_id}/lohnabrechnung.pdf`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-foreground hover:bg-muted"
          >
            <FileDown className="h-4 w-4" aria-hidden="true" />
            Abrechnung als PDF
          </a>
        )}
      </div>

      {p.laufFehler && (
        <p role="alert" className="mt-4 rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm text-foreground">
          {p.laufFehler}
        </p>
      )}

      {p.lauf && <Lohnzettel lauf={p.lauf} />}
    </section>
  );
}

function Lohnzettel({ lauf }: { lauf: Lohnlauf }) {
  const teilmonat = anteilSatz(lauf);
  return (
    <div className="mt-6 rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">
          {lauf.mitarbeiter} · {lauf.periode}
        </h3>
        <Badge tone={istAbgerechnet(lauf) ? "success" : "neutral"}>
          {istAbgerechnet(lauf) ? "abgerechnet" : "Vorschau"}
        </Badge>
      </div>
      {teilmonat && <p className="mb-3 text-xs text-muted-foreground">{teilmonat}</p>}

      <Zeile label="Grundlohn" betrag={lauf.grundlohn} />
      {lauf.dreizehnter > 0 && <Zeile label="13. Monatslohn" betrag={lauf.dreizehnter} />}
      {lauf.zulagen > 0 && <Zeile label="Zulagen" betrag={lauf.zulagen} />}
      {lauf.kinderzulagen > 0 && <Zeile label="Kinderzulagen" betrag={lauf.kinderzulagen} />}
      <Zeile label="Bruttolohn" betrag={lauf.brutto} stark />

      <p className="mt-4 mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Abzüge</p>
      {lauf.abzuege.map((a) => (
        <Zeile key={a.label} label={a.label} zusatz={satzLabel(a.satz)} betrag={-a.betrag} />
      ))}
      <Zeile label="Nettolohn" betrag={lauf.netto} stark />

      <p className="mt-4 mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Arbeitgeberbeiträge
      </p>
      {lauf.arbeitgeber.map((a) => (
        <Zeile key={a.label} label={a.label} zusatz={satzLabel(a.satz)} betrag={a.betrag} />
      ))}
      <Zeile label="Total Arbeitgeber" betrag={lauf.ag_total} stark />

      <p className="mt-4 text-xs text-muted-foreground">{nettoSatz(lauf)}</p>
    </div>
  );
}

function Zeile({
  label,
  betrag,
  zusatz,
  stark = false,
}: {
  label: string;
  betrag: number;
  zusatz?: string;
  stark?: boolean;
}) {
  return (
    <div className={`flex justify-between gap-4 py-1 text-sm ${stark ? "border-t border-border pt-2 font-semibold" : ""}`}>
      <span className="text-foreground">
        {label}
        {zusatz && <span className="ml-2 text-xs text-muted-foreground">{zusatz}</span>}
      </span>
      <span className="tabular-nums text-foreground">{formatCHF(betrag)}</span>
    </div>
  );
}
