export interface ReviewItem {
  id: number;
  beschreibung: string;
  betrag: number;
  predicted_soll: string;
  predicted_haben: string;
  predicted_mwst_code: string;
  predicted_mwst_pct: string;
  confidence: number;
  source: string;
  status: string;
  created_at: string | null;
}

export interface ReviewQueue {
  items: ReviewItem[];
  threshold?: number;
}
