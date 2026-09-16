"use client";

import { FilePlus2, Save, Settings2 } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button, ButtonLink } from "@/components/ui/Button";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { useRechnungSchreiben } from "./hooks/useRechnungSchreiben";
import { KundeFelder } from "./components/KundeFelder";
import { PositionenEditor } from "./components/PositionenEditor";
import { RechnungFertig } from "./components/RechnungFertig";
import { VersandDialog } from "@/app/dashboard/components/VersandDialog";
import { useVersand } from "../hooks/useVersand";

export default function RechnungSchreibenPage() {
  const r = useRechnungSchreiben();
  const versand = useVersand();

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FilePlus2}
        title="Rechnung schreiben"
        subtitle="Kunde und Positionen erfassen — daraus entstehen QR-Rechnung, Debitorenbuchung und offener Posten"
        action={
          !r.rechnung && (
            <Button
              variant="primary"
              onClick={r.speichern}
              loading={r.saving}
              disabled={r.saving || r.fehlt.length > 0 || !r.firma?.bereit}
              icon={<Save className="h-4 w-4" />}
            >
              Rechnung erstellen
            </Button>
          )
        }
      />

      {r.isLoading ? (
        <PageSkeleton rows={4} />
      ) : r.error ? (
        <ErrorState error={r.error} onRetry={r.retry} />
      ) : r.rechnung ? (
        <RechnungFertig
          rechnung={r.rechnung}
          onPrint={r.druckansicht}
          onPdf={r.pdf}
          onSenden={() => versand.oeffnen(r.rechnung!.document.id)}
          sendenBusy={versand.loadingId === r.rechnung.document.id}
          onNeu={r.neueRechnung}
        />
      ) : (
        <>
          {!r.firma?.bereit && (
            <div role="status" className="rounded-xl border border-warning/30 bg-warning/5 p-5">
              <h2 className="text-sm font-semibold text-foreground">Firmenprofil zuerst vervollständigen</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Für den Zahlteil fehlt noch: {r.firma?.fehlt?.join(", ") || "Firmenprofil"}. Ohne IBAN gibt es
                keinen QR-Code und keine Referenz, die die Zahlung später von selbst zuordnet.
              </p>
              <ButtonLink
                variant="secondary"
                size="sm"
                href="/dashboard/belege/firma"
                className="mt-4"
                icon={<Settings2 className="h-4 w-4" />}
              >
                Firmenprofil öffnen
              </ButtonLink>
            </div>
          )}

          <KundeFelder kunde={r.kunde} onChange={r.setKundeField} />

          <PositionenEditor
            rows={r.rows}
            summe={r.summe}
            onChange={r.setRow}
            onAdd={r.addRow}
            onRemove={r.removeRow}
          />

          <section aria-labelledby="hinweis-titel" className="rounded-xl border border-border bg-card p-6">
            <h2 id="hinweis-titel" className="text-base font-semibold text-foreground">Bemerkung</h2>
            <p className="mt-0.5 mb-3 text-sm text-muted-foreground">
              Steht als zusätzliche Information auf der Rechnung (max. 140 Zeichen).
            </p>
            <input
              aria-label="Bemerkung"
              value={r.bemerkung}
              maxLength={140}
              onChange={(e) => r.setBemerkung(e.target.value)}
              placeholder="Vielen Dank für Ihren Auftrag"
              className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {r.fehlt.length > 0 && (
              <p className="mt-4 text-sm text-muted-foreground">Es fehlt noch: {r.fehlt.join(", ")}.</p>
            )}
          </section>
        </>
      )}

      <VersandDialog
        draft={versand.draft}
        sending={versand.sending}
        onClose={versand.schliessen}
        onSend={versand.senden}
      />
    </div>
  );
}
