"use client";

import { Building2, Check, Save } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { SettingsField, SettingsInput } from "../../settings/components/SettingsPrimitives";
import { useFirma } from "./hooks/useFirma";
import { adressWarnung } from "./adresse";

export default function FirmaPage() {
  const f = useFirma();
  // B-103: the one combination that produced a Zahlteil nobody could post to.
  const strassenWarnung = adressWarnung(f.entwurf.strasse, f.entwurf.hausnummer);
  // B-104/B-105: `fehlt` names the field; show it *at* the field, not only above.
  const fehlt = (feld: string) => (f.profil?.fehlt ?? []).some((m) => m.startsWith(feld));

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Building2}
        title="Firmenprofil"
        subtitle="Absender und Zahlteil der Rechnungen, die wir selber schreiben"
        action={
          <Button
            variant={f.saved ? "success" : "primary"}
            onClick={f.speichern}
            loading={f.saving}
            disabled={f.saving}
            icon={f.saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          >
            {f.saved ? "Gespeichert" : "Speichern"}
          </Button>
        }
      />

      {f.isLoading ? (
        <PageSkeleton rows={4} />
      ) : f.error ? (
        <ErrorState error={f.error} onRetry={f.retry} />
      ) : (
        <>
          <div
            role="status"
            className={`rounded-xl border p-5 ${f.profil?.bereit ? "border-success/30 bg-success/5" : "border-warning/30 bg-warning/5"}`}
          >
            <p className="text-sm text-foreground">
              {f.profil?.bereit
                ? `Bereit für QR-Rechnungen — Referenzart ${f.profil?.referenz_typ}${f.profil?.qr_iban ? " (QR-IBAN)" : ""}.`
                : `Noch nicht bereit. Es fehlt: ${f.profil?.fehlt?.join(", ") || "Firmenprofil"}.`}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Mit einer QR-IBAN wird eine QRR-Referenz gedruckt, mit einer normalen IBAN eine SCOR-Referenz.
              Beide kommen auf dem Kontoauszug zurück und der Abgleich erkennt sie exakt.
            </p>
          </div>

          <section aria-labelledby="adresse-titel" className="rounded-xl border border-border bg-card p-6">
            <h2 id="adresse-titel" className="mb-2 text-base font-semibold text-foreground">Adresse und Kontakt</h2>
            <SettingsField
              label="Firmenname"
              description="Steht als Zahlungsempfänger im Zahlteil"
              required
              htmlFor="firma-name"
              error={fehlt("Firmenname") ? "Ohne Firmenname kann kein Zahlteil gedruckt werden." : ""}
            >
              <SettingsInput id="firma-name" label="Firmenname" value={f.entwurf.name} onChange={(v) => f.setFeld("name", v)} invalid={fehlt("Firmenname")} />
            </SettingsField>
            {/* B-103: two fields, two labels, two placeholders — and a warning when
                both would end up in the QR code. */}
            <SettingsField
              label="Strasse"
              description="Nur der Strassenname — die Nummer kommt ins Feld daneben"
              required
              htmlFor="firma-strasse"
              error={strassenWarnung}
            >
              <div className="flex gap-2">
                <SettingsInput
                  id="firma-strasse"
                  label="Strasse"
                  value={f.entwurf.strasse}
                  onChange={(v) => f.setFeld("strasse", v)}
                  placeholder="Bungertenstrasse"
                  invalid={Boolean(strassenWarnung)}
                  describedBy={strassenWarnung ? "firma-strasse-error" : undefined}
                />
                <div className="w-24">
                  <SettingsInput
                    id="firma-hausnummer"
                    label="Hausnummer"
                    value={f.entwurf.hausnummer}
                    onChange={(v) => f.setFeld("hausnummer", v)}
                    placeholder="Nr."
                    invalid={Boolean(strassenWarnung)}
                  />
                </div>
              </div>
            </SettingsField>
            <SettingsField
              label="PLZ und Ort"
              required
              htmlFor="firma-plz"
              error={fehlt("Adresse") ? "PLZ und Ort stehen im Zahlteil — beide werden gebraucht." : ""}
            >
              <div className="flex gap-2">
                <div className="w-28">
                  <SettingsInput id="firma-plz" label="PLZ" value={f.entwurf.plz} onChange={(v) => f.setFeld("plz", v)} placeholder="8307" invalid={fehlt("Adresse")} />
                </div>
                <SettingsInput label="Ort" value={f.entwurf.ort} onChange={(v) => f.setFeld("ort", v)} placeholder="Illnau-Effretikon" invalid={fehlt("Adresse")} />
              </div>
            </SettingsField>
            <SettingsField label="E-Mail">
              <SettingsInput label="E-Mail" type="email" value={f.entwurf.email} onChange={(v) => f.setFeld("email", v)} />
            </SettingsField>
            <SettingsField label="Telefon">
              <SettingsInput label="Telefon" value={f.entwurf.telefon} onChange={(v) => f.setFeld("telefon", v)} />
            </SettingsField>
            {/* B-104: required exactly when the invoice shows a rate — the rate and
                the number are one statement, and the product used to make half of it. */}
            <SettingsField
              label="MWST-Nummer"
              description="z. B. CHE-123.456.789 MWST — nötig, sobald die Rechnung einen MWST-Satz ausweist"
              required={fehlt("MWST-Nummer")}
              htmlFor="firma-mwst-nr"
              error={fehlt("MWST-Nummer") ? "Die Rechnung weist MWST aus. Dann gehört die Nummer auf die Rechnung — oder der Satz unter «Buchung» muss leer sein." : ""}
            >
              <SettingsInput id="firma-mwst-nr" label="MWST-Nummer" value={f.entwurf.mwst_nr} onChange={(v) => f.setFeld("mwst_nr", v)} placeholder="CHE-123.456.789 MWST" invalid={fehlt("MWST-Nummer")} />
            </SettingsField>
          </section>

          <section aria-labelledby="zahlung-titel" className="rounded-xl border border-border bg-card p-6">
            <h2 id="zahlung-titel" className="mb-2 text-base font-semibold text-foreground">Zahlung</h2>
            <SettingsField
              label="IBAN"
              description={f.profil?.iban_formatiert || "CH.. oder LI.., QR-IBAN wird erkannt"}
              required
              htmlFor="firma-iban"
              error={fehlt("IBAN") ? "Ohne gültige IBAN gibt es keinen Zahlteil." : ""}
            >
              <SettingsInput id="firma-iban" label="IBAN" value={f.entwurf.iban} onChange={(v) => f.setFeld("iban", v)} placeholder="CH44 3199 9123 0008 8901 2" invalid={fehlt("IBAN")} />
            </SettingsField>
            <SettingsField label="Zahlungsfrist (Tage)" description="Bestimmt das Fälligkeitsdatum">
              <SettingsInput label="Zahlungsfrist in Tagen" value={f.entwurf.zahlungsfrist_tage} onChange={(v) => f.setFeld("zahlungsfrist_tage", v)} />
            </SettingsField>
          </section>

          <section aria-labelledby="konten-titel" className="rounded-xl border border-border bg-card p-6">
            <h2 id="konten-titel" className="mb-2 text-base font-semibold text-foreground">Buchung</h2>
            <p className="mb-2 text-sm text-muted-foreground">
              Die Rechnung wird am Rechnungsdatum auf Debitoren gebucht, die Zahlung später auf das Bankkonto.
            </p>
            <SettingsField label="Debitorenkonto" description="Soll bei der Rechnung">
              <SettingsInput label="Debitorenkonto" value={f.entwurf.konto_debitoren} onChange={(v) => f.setFeld("konto_debitoren", v)} />
            </SettingsField>
            <SettingsField label="Ertragskonto" description="Haben bei der Rechnung">
              <SettingsInput label="Ertragskonto" value={f.entwurf.konto_ertrag} onChange={(v) => f.setFeld("konto_ertrag", v)} />
            </SettingsField>
            <SettingsField label="Bankkonto" description="Soll bei der Zahlung">
              <SettingsInput label="Bankkonto" value={f.entwurf.konto_bank} onChange={(v) => f.setFeld("konto_bank", v)} />
            </SettingsField>
            <SettingsField label="MWST-Code" description="Umsatzcode, z. B. V81 — leer lassen, wenn nicht MWST-pflichtig">
              <SettingsInput label="MWST-Code" value={f.entwurf.mwst_code} onChange={(v) => f.setFeld("mwst_code", v)} />
            </SettingsField>
            <SettingsField label="MWST-Satz" description="z. B. -8.10 für 8.1 % Umsatzsteuer">
              <SettingsInput label="MWST-Satz" value={f.entwurf.mwst_pct} onChange={(v) => f.setFeld("mwst_pct", v)} />
            </SettingsField>
          </section>

          <section aria-labelledby="steuer-titel" className="rounded-xl border border-border bg-card p-6">
            <h2 id="steuer-titel" className="mb-2 text-base font-semibold text-foreground">Gewinnsteuer</h2>
            <p className="mb-2 text-sm text-muted-foreground">
              Für die Steuerrückstellung auf <em>Heute</em>. Die effektive Belastung (Bund, Kanton, Gemeinde)
              lag 2026 zwischen 11.66 % (Luzern) und 20.54 % (Bern), im Mittel 14.43 % — den Satz für Ihre
              Gemeinde nennt Ihr Treuhänder. Leer lassen heisst: es wird nichts geschätzt.
            </p>
            <SettingsField label="Gewinnsteuersatz (%)" description="Effektiv, inkl. Bundessteuer — z. B. 14.43">
              <SettingsInput
                label="Gewinnsteuersatz in Prozent"
                value={f.entwurf.gewinnsteuer_satz}
                onChange={(v) => f.setFeld("gewinnsteuer_satz", v)}
                placeholder="14.43"
              />
            </SettingsField>
          </section>
        </>
      )}
    </div>
  );
}
