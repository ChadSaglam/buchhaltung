import type { LearningStatsResponse } from "@/lib/api-schema";

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

/** B-59: generated from the backend schema — memory/corrections are keyed by
 *  account, bookings by source, and the API says so. */
export type LearningStats = LearningStatsResponse;

/** What a bar chart needs, after the caller has picked which key is the label. */
export interface ChartBar {
  label: string;
  count: number;
}

export interface LernverlaufData {
  memory: MemoryEntry[];
  corrections: CorrectionEntry[];
  stats: LearningStats;
  info: { memory_count: number; correction_count: number };
}

export type LernverlaufTab = "charts" | "memory" | "corrections";
