"use client";

import { ShieldCheck, ShieldAlert, Shield } from "lucide-react";
import type { BvgPruefungOut } from "@/lib/api-schema";

/**
 * Das gesetzliche BVG-Minimum gegen die eingetragenen Beträge (B-72, Option C).
 *
 * Steht bewusst *neben* der Abrechnung und nicht darin: die Altersgutschrift
 * kommt weiterhin von der Pensionskasse. Was hier steht, ist der Widerspruch
 * zum Obligatorium — die einzige BVG-Zahl, die das Gesetz selbst hergibt.
 */
export function BvgPruefung({ pruefung }: { pruefung: BvgPruefungOut | undefined }) {
  if (!pruefung) return null;

  // B-95: a check over nobody is not a passed check. Green here on an empty
  // tenant was the first thing a new user saw on this page, and it was the
  // same shape as an RLS check passing on an empty database.
  const leer = (pruefung.geprueft ?? 0) === 0;
  const sauber = !leer && pruefung.hinweise.length === 0;
  const Icon = leer ? Shield : sauber ? ShieldCheck : ShieldAlert;

  return (
    <section
      aria-labelledby="bvg-titel"
      className={`rounded-xl border p-6 ${sauber ? "border-border bg-card" : "border-warning/30 bg-warning/5"}`}
    >
      <div className="flex items-start gap-3">
        <Icon
          className={`mt-0.5 h-5 w-5 shrink-0 ${leer ? "text-muted-foreground" : sauber ? "text-success" : "text-warning"}`}
          aria-hidden="true"
        />
        <div className="min-w-0">
          <h2 id="bvg-titel" className="text-base font-semibold text-foreground">
            BVG-Obligatorium {pruefung.jahr}
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Geprüft gegen die Grenzbeträge {pruefung.grenzbetraege_jahr} und die Altersgutschriftensätze nach
            Art. 16 BVG. Die Beträge auf der Abrechnung kommen weiterhin von Ihrer Pensionskasse — hier steht
            nur, wo sie dem Gesetz widersprechen.
          </p>

          {leer ? (
            <p className="mt-3 text-sm text-muted-foreground">
              Noch nichts zu prüfen — es ist niemand angelegt.
            </p>
          ) : sauber ? (
            <p className="mt-3 text-sm text-foreground">
              Kein Widerspruch zum Obligatorium gefunden — {pruefung.geprueft}{" "}
              {pruefung.geprueft === 1 ? "Person" : "Personen"} geprüft.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {pruefung.hinweise.map((h, i) => (
                <li key={`${h.code}-${h.mitarbeiter_id ?? "alle"}-${i}`} className="text-sm text-foreground">
                  {h.text}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
