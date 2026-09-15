import { CheckCircle2, Printer, Plus } from "lucide-react";
import { Button, ButtonLink } from "@/components/ui/Button";
import { chf } from "../helpers";
import type { RechnungOut } from "../types";

export function RechnungFertig({ rechnung, onPrint, onNeu }: {
  rechnung: RechnungOut;
  onPrint: () => void;
  onNeu: () => void;
}) {
  const doc = rechnung.document;
  return (
    <section aria-labelledby="fertig-titel" className="rounded-xl border border-success/30 bg-success/5 p-6">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
        <div className="min-w-0">
          <h2 id="fertig-titel" className="text-base font-semibold text-foreground">
            Rechnung {doc.invoice_no} über CHF {chf(rechnung.total)}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Gebucht auf Debitoren, fällig am{" "}
            {doc.due_date ? new Date(doc.due_date).toLocaleDateString("de-CH") : "—"}. Sobald die Zahlung mit
            dieser Referenz auf dem Kontoauszug erscheint, schlägt der Abgleich sie von selbst vor.
          </p>
          <dl className="mt-4 grid grid-cols-1 gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Referenz ({rechnung.referenz_typ})</dt>
              <dd className="font-mono text-foreground">{rechnung.referenz_formatiert || "—"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Kunde</dt>
              <dd className="truncate text-foreground">{doc.vendor}</dd>
            </div>
          </dl>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="primary" icon={<Printer className="h-4 w-4" />} onClick={onPrint}>
              Rechnung drucken
            </Button>
            <Button variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={onNeu}>
              Nächste Rechnung
            </Button>
            <ButtonLink variant="ghost" href="/dashboard/rechnungen">
              Zur Übersicht
            </ButtonLink>
          </div>
        </div>
      </div>
    </section>
  );
}
