export interface MemoryEntry {
  lookup_key: string;
  kt_soll: string;
  kt_haben: string;
  mwst_code: string;
  mwst_pct: string;
}

export interface CorrectionEntry {
  beschreibung: string;
  original_soll: string;
  original_haben: string;
  corrected_soll: string;
  corrected_haben: string;
  corrected_mwst_code: string;
  created_at: string | null;
}

export interface ChartItem {
  account?: string;
  source?: string;
  count: number;
}

export interface LearningStats {
  memory_count: number;
  correction_count: number;
  booking_count: number;
  memory_distribution: ChartItem[];
  correction_distribution: ChartItem[];
  source_distribution: ChartItem[];
}

export interface LernverlaufData {
  memory: MemoryEntry[];
  corrections: CorrectionEntry[];
  stats: LearningStats;
  info: { memory_count: number; correction_count: number };
}

export type LernverlaufTab = "charts" | "memory" | "corrections";
