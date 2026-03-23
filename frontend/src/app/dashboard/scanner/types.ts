export interface OllamaStatus {
  ok: boolean;
  error?: string;
  models?: { name: string }[];
  vision_models?: string[];
  best_vision?: string | null;
}

export interface ExtractedInvoice {
  vendor: string;
  date: string;
  invoice_number: string;
  description: string;
  total_amount: number;
  vat_rate: number;
  line_items: { item: string; amount: number }[];
  kt_soll?: string;
  kt_haben?: string;
  mwst_code?: string;
  mwst_pct?: string;
  mwst_amount?: number;
  classification_confidence?: number;
  classification_source?: string;
}

export interface ClassificationResult {
  kt_soll: string;
  kt_soll_name: string;
  kt_haben: string;
  kt_haben_name: string;
  mwst_code: string;
  mwst_pct: string;
  mwst_amount: number;
  confidence: number;
  source: string;
}

export interface BuchungRow {
  nr: number;
  datum: string;
  beleg: string;
  rechnung: string;
  beschreibung: string;
  kt_soll: string;
  kt_haben: string;
  betrag: number;
  mwstcode: string;
  artbetrag: string;
  mwstpct: string;
  mwstchf: number | string;
  ks3: string;
}

export const MWST_CODE_OPTIONS = ["", "V81", "M81", "I81", "V77", "M77", "I77", "V25", "M25", "I25", "I26"];
export const MWST_PCT_OPTIONS = ["", "8.10", "7.70", "2.60", "2.50", "-8.10", "-7.70"];

export type ScannerStep = "upload" | "processing" | "review" | "saved";
