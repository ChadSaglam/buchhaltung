"use client";

import { useRef, useState } from "react";
import toast from "react-hot-toast";
import { FileUp, Upload } from "lucide-react";
import { api } from "@/lib/api";
import type { KontenplanImportErgebnis, KontenplanImportVorschau } from "@/lib/api-schema";
import { errorMessage } from "@/lib/errors";
import {
  STATUS_LABEL,
  STATUS_TON,
  doppelteSatz,
  doppelteZeilen,
  danach,
  folgenSatz,
  istWirkungslos,
  sortiert,
  verliertDaten,
  type ImportModus,
} from "@/lib/kontenplan_import";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

/**
 * Kontenplan aus einer Datei übernehmen (B-20, letztes Drittel).
 *
 * Drei Schritte, weil der Schreibvorgang zerstörend sein kann: Datei wählen →
 * sehen, was passieren würde → entscheiden. Der zweite Schritt schreibt nichts;
 * er ist der ganze Grund, warum das ein Assistent ist und kein Knopf.
 */
export function ImportAssistent({ bestand, onFertig }: { bestand: number; onFertig: () => void }) {
  const [datei, setDatei] = useState<File | null>(null);
  const [vorschau, setVorschau] = useState<KontenplanImportVorschau | null>(null);
  const [modus, setModus] = useState<ImportModus>("ergaenzen");
  const [busy, setBusy] = useState(false);
  const [bestaetigt, setBestaetigt] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const zuruecksetzen = () => {
    setDatei(null);
    setVorschau(null);
    setBestaetigt(false);
    if (inputRef.current) inputRef.current.value = "";
  };

  const lesen = async (f: File) => {
    setBusy(true);
    setVorschau(null);
    setBestaetigt(false);
    try {
      const form = new FormData();
      form.append("file", f);
      const { data } = await api.post<KontenplanImportVorschau>("/api/kontenplan/import/vorschau", form);
      setVorschau(data);
      setDatei(f);
    } catch (e) {
      toast.error(errorMessage(e));
      zuruecksetzen();
    } finally {
      setBusy(false);
    }
  };

  const uebernehmen = async () => {
    if (!datei || !vorschau) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", datei);
      form.append("modus", modus);
      const { data } = await api.post<KontenplanImportErgebnis>("/api/kontenplan/import", form);
      toast.success(
        `${data.count} Konten im Plan — ${data.neu} neu, ${data.geaendert} geändert` +
          (data.entfernt ? `, ${data.entfernt} entfernt` : ""),
      );
      zuruecksetzen();
      onFertig();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const gefaehrlich = vorschau ? verliertDaten(vorschau, modus) : false;
  const wirkungslos = vorschau ? istWirkungslos(vorschau, modus) : true;

  return (
    <section aria-labelledby="import-titel" className="rounded-xl border border-border bg-card p-6">
      <h2 id="import-titel" className="text-base font-semibold text-foreground">
        Kontenplan übernehmen
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Eine CSV- oder Excel-Datei mit einer Spalte für die Kontonummer und einer für die Bezeichnung — der
        Konten-Export aus Banana oder dem alten Programm passt so, wie er ist. Sie sehen zuerst, was passieren
        würde.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {/* The visible control is the button below; the input still needs its own
            label, because a screen reader lands on the input, not on the button. */}
        <label htmlFor="kontenplan-datei" className="sr-only">
          Kontenplan-Datei (CSV oder Excel)
        </label>
        <input
          ref={inputRef}
          id="kontenplan-datei"
          type="file"
          accept=".csv,.txt,.xls,.xlsx"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void lesen(f);
          }}
        />
        <Button
          variant="outline"
          size="sm"
          icon={<FileUp className="h-4 w-4" aria-hidden="true" />}
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          Datei wählen
        </Button>
        {datei && <span className="text-sm text-muted-foreground">{datei.name}</span>}
        {vorschau && (
          <button type="button" onClick={zuruecksetzen} className="text-sm text-muted-foreground hover:underline">
            Andere Datei
          </button>
        )}
      </div>

      {vorschau && (
        <div className="mt-5 space-y-4">
          <p className="text-xs text-muted-foreground">
            Gelesen als «{vorschau.spalte_konto}» und «{vorschau.spalte_bezeichnung}».
          </p>

          <div className="flex flex-wrap gap-2">
            {(["neu", "geaendert", "unveraendert", "ungueltig"] as const).map((s) => (
              <Badge key={s} tone={STATUS_TON[s]}>
                {vorschau.zaehler[s]} {STATUS_LABEL[s]}
              </Badge>
            ))}
            {doppelteZeilen(vorschau).length > 0 && (
              <Badge tone="warning">{doppelteZeilen(vorschau).length} doppelt benannt</Badge>
            )}
          </div>

          {/* B-85: 2200 und 2205 heissen beide «Geschuldete MWST». Sagen, nicht handeln. */}
          {doppelteSatz(vorschau, modus) && (
            <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs leading-snug text-foreground">
              {doppelteSatz(vorschau, modus)}
            </p>
          )}

          <div className="max-h-72 overflow-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <caption className="sr-only">Zeilen der hochgeladenen Datei und was mit ihnen geschieht</caption>
              <thead className="sticky top-0 bg-muted text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Konto</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Bezeichnung</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Was passiert</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortiert(vorschau.zeilen).map((z) => (
                  <tr key={`${z.konto}-${z.quelle}`}>
                    <td className="px-3 py-2 font-mono text-xs text-foreground">{z.konto}</td>
                    <td className="px-3 py-2 text-foreground">
                      {z.bezeichnung || <span className="text-muted-foreground">—</span>}
                      {z.status === "geaendert" && (
                        <span className="ml-2 text-xs text-muted-foreground">bisher: {z.bisher}</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <Badge tone={STATUS_TON[z.status]}>{STATUS_LABEL[z.status]}</Badge>
                      {z.grund && <span className="ml-2 text-xs text-muted-foreground">{z.grund}</span>}
                      {z.doppelt_zu && modus === "ergaenzen" && (
                        <span className="ml-2 text-xs text-warning">heisst gleich wie {z.doppelt_zu}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-foreground">Wie übernehmen?</legend>
            {(["ergaenzen", "ersetzen"] as const).map((m) => (
              <label key={m} className="flex items-start gap-2 text-sm text-foreground">
                <input
                  type="radio"
                  name="import-modus"
                  value={m}
                  checked={modus === m}
                  onChange={() => {
                    setModus(m);
                    setBestaetigt(false);
                  }}
                  className="mt-1"
                />
                <span>
                  {m === "ergaenzen" ? "Ergänzen" : "Ersetzen"}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {m === "ergaenzen"
                      ? "Konten aus der Datei anlegen oder aktualisieren, alles Übrige bleibt stehen."
                      : "Der Kontenplan ist danach genau die Datei — was nicht darin steht, wird gelöscht."}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>

          <div
            role="status"
            className={`rounded-lg border p-4 text-sm ${
              gefaehrlich ? "border-destructive/30 bg-destructive/5 text-foreground" : "border-border bg-surface"
            }`}
          >
            <p>{folgenSatz(vorschau, modus)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Der Kontenplan hat danach {danach(vorschau, modus, bestand)} Konten (heute {bestand}).
            </p>
            {gefaehrlich && (
              <>
                <p className="mt-2 text-xs text-muted-foreground">
                  Gelöscht würden: {vorschau.entfaellt.join(", ")}
                </p>
                <label className="mt-3 flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={bestaetigt}
                    onChange={(e) => setBestaetigt(e.target.checked)}
                  />
                  Ja, diese Konten dürfen verschwinden.
                </label>
              </>
            )}
          </div>

          <Button
            variant="primary"
            icon={<Upload className="h-4 w-4" aria-hidden="true" />}
            onClick={uebernehmen}
            loading={busy}
            disabled={busy || wirkungslos || (gefaehrlich && !bestaetigt)}
          >
            {wirkungslos ? "Nichts zu übernehmen" : "Übernehmen"}
          </Button>
        </div>
      )}
    </section>
  );
}
