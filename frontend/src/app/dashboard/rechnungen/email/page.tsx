"use client";

import { Mail, Save, Check, RefreshCw, Power } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageSkeleton } from "@/components/shared/PageSkeleton";
import { useEmailEingang } from "./hooks/useEmailEingang";
import { NachrichtenListe } from "./components/NachrichtenListe";

export default function EmailEingangPage() {
  const e = useEmailEingang();
  const s = e.data?.einstellungen;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Mail}
        title="E-Mail-Eingang"
        subtitle="Belege weiterleiten statt herunterladen und wieder hochladen"
        action={
          s?.imap && (
            <Button
              variant="secondary"
              onClick={e.jetztAbrufen}
              loading={e.fetching}
              disabled={e.fetching}
              icon={<RefreshCw className="h-4 w-4" />}
            >
              Jetzt abrufen
            </Button>
          )
        }
      />

      {e.isLoading ? (
        <PageSkeleton rows={4} />
      ) : e.error ? (
        <ErrorState error={e.error} onRetry={e.retry} />
      ) : (
        <>
          <section aria-labelledby="adresse-titel" className="rounded-xl border border-border bg-card p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="adresse-titel" className="text-base font-semibold text-foreground">Deine Adresse</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Alles, was hier ankommt, landet als Beleg unter <em>Rechnungen</em>.
                </p>
              </div>
              <Badge tone={s?.aktiv ? "success" : "neutral"}>{s?.aktiv ? "Eingeschaltet" : "Ausgeschaltet"}</Badge>
            </div>

            {s?.bereit ? (
              <p className="mt-4 select-all break-all rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm text-foreground">
                {s.adresse}
              </p>
            ) : (
              <p className="mt-4 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm text-foreground">
                Für diese Installation ist noch keine E-Mail-Domain hinterlegt
                (<code className="font-mono text-xs">EMAIL_INTAKE_DOMAIN</code>), darum gibt es noch keine Adresse.
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>Postfach-Abruf: {s?.imap ? "aktiv" : "nicht konfiguriert"}</span>
              <span aria-hidden="true">·</span>
              <span>Webhook: {s?.webhook ? "aktiv" : "nicht konfiguriert"}</span>
            </div>

            <Button
              variant="ghost"
              size="sm"
              className="mt-4"
              icon={<Power className="h-4 w-4" />}
              onClick={e.umschalten}
            >
              {s?.aktiv ? "Ausschalten" : "Einschalten"}
            </Button>
          </section>

          <section aria-labelledby="absender-titel" className="rounded-xl border border-border bg-card p-6">
            <h2 id="absender-titel" className="text-base font-semibold text-foreground">Wer darf schicken</h2>
            <p className="mt-0.5 mb-4 text-sm text-muted-foreground">
              Eine Adresse pro Zeile, oder eine ganze Domain als <code className="font-mono text-xs">@lieferant.ch</code>.
              Solange die Liste leer ist, wird nichts übernommen — die Adresse ist erratbar.
            </p>
            <textarea
              aria-label="Erlaubte Absender"
              value={e.allowList}
              onChange={(ev) => e.setAllowList(ev.target.value)}
              rows={5}
              placeholder={"rechnung@lieferant.ch\n@treuhand.ch"}
              className="w-full rounded-lg border border-input bg-surface px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <Button
              variant={e.saved ? "success" : "primary"}
              className="mt-4"
              onClick={e.speichern}
              loading={e.saving}
              disabled={e.saving}
              icon={e.saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            >
              {e.saved ? "Gespeichert" : "Speichern"}
            </Button>
          </section>

          <section aria-labelledby="nachrichten-titel" className="rounded-xl border border-border bg-card p-6">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="nachrichten-titel" className="text-base font-semibold text-foreground">Zuletzt angekommen</h2>
              <p className="text-sm text-muted-foreground">
                {e.data?.belege_24h ?? 0} Beleg(e) in 24 Stunden
                {e.data?.abgelehnt ? ` · ${e.data.abgelehnt} abgelehnt` : ""}
              </p>
            </div>
            <NachrichtenListe
              nachrichten={e.data?.nachrichten ?? []}
              absender={s?.absender ?? []}
              onErlauben={e.absenderErlauben}
            />
          </section>
        </>
      )}
    </div>
  );
}
