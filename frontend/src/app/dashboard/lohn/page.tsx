"use client";

import { FileDown, Wallet } from "lucide-react";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { PageHeader } from "@/components/ui/page_header";
import { API_URL } from "@/lib/api";
import { formatCHF } from "@/lib/format";
import { anzeigeName, bereitschaftSatz, bereitschaftTone, periodeLabel } from "@/lib/lohn";
import { AbrechnungPanel } from "./components/AbrechnungPanel";
import { BvgPruefung } from "./components/BvgPruefung";
import { MitarbeiterListe } from "./components/MitarbeiterListe";
import { RatenForm } from "./components/RatenForm";
import { useLohn } from "./hooks/useLohn";

/**
 * Lohn (B-72).
 *
 * The page is ordered the way the work is: the rates first, because nothing
 * below them works until they are on file; then the people; then the month.
 * The readiness banner at the top is the only thing an owner has to read on a
 * first visit — it names every rate that is still missing, so the setup is one
 * pass and not four failed attempts.
 */
export default function LohnPage() {
  const l = useLohn();
  const tone = bereitschaftTone(l.settings);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Wallet}
        title="Lohn"
        subtitle="Bruttolohn, Abzüge, Auszahlung — und die Buchungen dazu"
      />

      {l.isLoading ? (
        <PageSkeleton rows={4} />
      ) : l.error ? (
        <ErrorState error={l.error} onRetry={l.retry} />
      ) : (
        <>
          <div
            role="status"
            className={`rounded-xl border p-5 ${
              tone === "success" ? "border-success/30 bg-success/5" : "border-warning/30 bg-warning/5"
            }`}
          >
            <p className="text-sm text-foreground">{bereitschaftSatz(l.settings)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              AHV/IV/EO und ALV sind für alle gleich und bereits hinterlegt. Die übrigen Sätze stehen im
              Vertrag mit Ihrer Versicherung oder werden vom Kanton bestimmt; ohne sie wird keine
              Abrechnung erstellt, weil eine geschätzte Prämie wie eine richtige aussieht.
            </p>
          </div>

          <RatenForm settings={l.settings} onSave={l.saetzeSpeichern} onFreigeben={l.freigeben} />

          <MitarbeiterListe liste={l.mitarbeiter} onCreate={l.mitarbeiterAnlegen} />

          <BvgPruefung pruefung={l.bvg} />

          <AbrechnungPanel
            waehlbar={l.waehlbar}
            gewaehlt={l.gewaehlt}
            setGewaehlt={l.setGewaehlt}
            jahr={l.jahr}
            monat={l.monat}
            setJahr={l.setJahr}
            setMonat={l.setMonat}
            zulagen={l.zulagen}
            setZulagen={l.setZulagen}
            dreizehnter={l.dreizehnter}
            setDreizehnter={l.setDreizehnter}
            lauf={l.lauf}
            laufFehler={l.laufFehler}
            busy={l.busy}
            bereit={l.bereit}
            vorschau={l.vorschau}
            abrechnen={l.abrechnen}
          />

          <section aria-labelledby="jahr-titel" className="rounded-xl border border-border bg-card p-6">
            <h2 id="jahr-titel" className="mb-1 text-base font-semibold text-foreground">
              Abgerechnet {l.jahr}
            </h2>
            <p className="mb-4 text-xs text-muted-foreground">
              Der Jahreszusammenzug ist kein Lohnausweis — das ist das amtliche Formular 11. Er liefert
              die Zahlen dafür.
            </p>

            {(l.abrechnungen?.eintraege ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Noch nichts abgerechnet in {l.jahr}.</p>
            ) : (
              <>
                <ul className="divide-y divide-border">
                  {(l.abrechnungen?.eintraege ?? []).map((e) => (
                    <li key={e.id} className="flex items-center justify-between gap-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {anzeigeName(l.mitarbeiter.find((m) => m.id === e.mitarbeiter_id))}
                        </p>
                        <p className="text-xs text-muted-foreground">{periodeLabel(e.jahr, e.monat)}</p>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-sm tabular-nums text-foreground">{formatCHF(e.netto)}</span>
                        <a
                          href={`${API_URL}/api/lohn/abrechnungen/${e.id}/lohnabrechnung.pdf`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm text-brand-600 hover:underline dark:text-brand-300"
                        >
                          PDF
                        </a>
                      </div>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 flex items-center justify-between gap-4 border-t border-border pt-4">
                  <span className="text-sm text-muted-foreground">
                    Brutto {formatCHF(l.abrechnungen?.brutto_total)} · Netto{" "}
                    {formatCHF(l.abrechnungen?.netto_total)} · Arbeitgeber{" "}
                    {formatCHF(l.abrechnungen?.ag_total)}
                  </span>
                  {l.gewaehlt != null && (
                    <a
                      href={`${API_URL}/api/lohn/mitarbeiter/${l.gewaehlt}/jahr/${l.jahr}.pdf`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-foreground hover:bg-muted"
                    >
                      <FileDown className="h-4 w-4" aria-hidden="true" />
                      Jahreszusammenzug
                    </a>
                  )}
                </div>
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}
