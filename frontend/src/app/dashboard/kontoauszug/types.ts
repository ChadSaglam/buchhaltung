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
  accepted?: boolean;
}

export type ExportFormat = "banana" | "excel" | "csv";
