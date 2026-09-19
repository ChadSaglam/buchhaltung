/**
 * Der Kontenplan-Import-Assistent (B-20) — die Entscheidungen, ohne React.
 *
 * Die eine Frage, die der Assistent beantworten muss, ist nicht "wie parse ich
 * das", sondern **"was verliere ich"**: `PUT /api/kontenplan/` ersetzt den
 * ganzen Plan, also ist «ersetzen» ein Löschvorgang mit freundlichem Namen.
 */

import type { KontenplanImportVorschau, KontenplanImportZeile } from "@/lib/api-schema";

export type ImportModus = "ergaenzen" | "ersetzen";

export const STATUS_LABEL: Record<string, string> = {
  neu: "Neu",
  geaendert: "Geändert",
  unveraendert: "Unverändert",
  ungueltig: "Nicht gelesen",
};

export const STATUS_TON: Record<string, "success" | "info" | "neutral" | "warning"> = {
  neu: "success",
  geaendert: "info",
  unveraendert: "neutral",
  ungueltig: "warning",
};

/** Was der Import schreiben würde — ungültige Zeilen zählen nicht mit. */
export function uebernehmbar(v: KontenplanImportVorschau): number {
  return v.zaehler.neu + v.zaehler.geaendert + v.zaehler.unveraendert;
}

/** Wie viele Konten nach dem Import im Plan stehen. */
export function danach(v: KontenplanImportVorschau, modus: ImportModus, bestand: number): number {
  if (modus === "ersetzen") return uebernehmbar(v);
  return bestand + v.zaehler.neu;
}

/** Ob dieser Klick Konten löscht — die Frage, die den Bestätigungsdialog auslöst. */
export function verliertDaten(v: KontenplanImportVorschau, modus: ImportModus): boolean {
  return modus === "ersetzen" && v.entfaellt.length > 0;
}

/** Der Satz über dem Knopf. Er nennt die Zahl, die weh tut, zuerst. */
export function folgenSatz(v: KontenplanImportVorschau, modus: ImportModus): string {
  if (verliertDaten(v, modus)) {
    const n = v.entfaellt.length;
    return `${n} ${n === 1 ? "Konto wird gelöscht" : "Konten werden gelöscht"}, ` +
      `${v.zaehler.neu} neu, ${v.zaehler.geaendert} geändert.`;
  }
  if (modus === "ersetzen") {
    return `${v.zaehler.neu} neu, ${v.zaehler.geaendert} geändert, nichts wird gelöscht.`;
  }
  return `${v.zaehler.neu} neu, ${v.zaehler.geaendert} geändert, alles Übrige bleibt.`;
}

/** Nichts zu tun — dann soll der Knopf auch nicht einladen. */
export function istWirkungslos(v: KontenplanImportVorschau, modus: ImportModus): boolean {
  if (verliertDaten(v, modus)) return false;
  return v.zaehler.neu === 0 && v.zaehler.geaendert === 0;
}

/**
 * B-85: dieselbe Bezeichnung, zwei Nummern.
 *
 * `seed_tenant` legt Geschuldete MWST auf **2200**, echte Schweizer Kontenpläne
 * verwenden **2205**. Wer seinen richtigen Plan mit *Ergänzen* importiert, hat
 * danach beide — byte-gleich benannt, und nichts im Produkt zieht eines davon
 * vor. Die MWST-Abrechnung liest Konten, der Klassifizierer lernt Konten, und
 * wer nach Namen auswählt, wählt zufällig.
 *
 * Der Assistent sagt es und tut nichts: welche Nummer bleiben soll, weiss nur
 * der Mandant. Im Modus *Ersetzen* verschwindet das alte Konto ohnehin, also
 * ist die Warnung dort gegenstandslos.
 */
export function doppelteZeilen(v: KontenplanImportVorschau): KontenplanImportZeile[] {
  return v.zeilen.filter((z) => Boolean(z.doppelt_zu));
}

export function doppelteSatz(v: KontenplanImportVorschau, modus: ImportModus): string {
  if (modus === "ersetzen") return "";
  const zeilen = doppelteZeilen(v);
  if (zeilen.length === 0) return "";
  if (zeilen.length === 1) {
    const z = zeilen[0];
    return `${z.konto} «${z.bezeichnung}» heisst gleich wie Ihr bestehendes Konto ${z.doppelt_zu}. Nach dem Ergänzen stehen beide im Plan — entscheiden Sie, welche Nummer Sie behalten wollen.`;
  }
  return `${zeilen.length} Konten aus der Datei heissen gleich wie bestehende Konten unter anderer Nummer. Nach dem Ergänzen stehen jeweils beide im Plan.`;
}

/** Ungültige Zeilen zuerst: das ist das, was der Nutzer in seiner Datei reparieren muss. */
export function sortiert(zeilen: KontenplanImportZeile[]): KontenplanImportZeile[] {
  const rang: Record<string, number> = { ungueltig: 0, geaendert: 1, neu: 2, unveraendert: 3 };
  return [...zeilen].sort(
    (a, b) => (rang[a.status] ?? 9) - (rang[b.status] ?? 9) || a.konto.localeCompare(b.konto),
  );
}
