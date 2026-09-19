export interface TxRow {
  Nr: number;
  Datum: string;
  Beschreibung: string;
  KtSoll: string;
  KtHaben: string;
  "Betrag CHF": number;
  "MwStUSt-Code": string;
  "MwSt-%": string;
  "Gebuchte MwStUSt CHF": number;
  confidence?: number;
  source?: string;
  suggSoll?: string;
  suggHaben?: string;
  /** Description the tenant used for this amount before (Betrag-Gedächtnis); one click replaces the bank text. */
  vorschlag?: string;
  /** B-92: why this row carries no account. Set only when `KtSoll` came back empty. */
  begruendung?: string;
  accepted?: boolean;
}

export type ExportFormat = "banana" | "excel" | "csv";
