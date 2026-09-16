import type { Schemas } from "@/lib/api-schema";

export type FirmaProfil = Schemas["FirmaProfilOut"];
export type RechnungOut = Schemas["RechnungOut"];
export type PositionIn = Schemas["PositionIn"];
export type KundeIn = Schemas["KundeIn"];

/** One row in the editor — amounts are strings while the user types. */
export interface PositionRow {
  bezeichnung: string;
  menge: string;
  einheit: string;
  einzelpreis: string;
}

export interface KundeForm {
  name: string;
  strasse: string;
  hausnummer: string;
  plz: string;
  ort: string;
  email: string;
}

export const LEERE_POSITION: PositionRow = { bezeichnung: "", menge: "1", einheit: "", einzelpreis: "" };
export const LEERER_KUNDE: KundeForm = { name: "", strasse: "", hausnummer: "", plz: "", ort: "", email: "" };
