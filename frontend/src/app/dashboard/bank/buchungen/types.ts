export type MetricTone = "up" | "down";

export interface AiSummaryState {
  summary: string | null;
  summaryFallback: boolean;
  summarizing: boolean;
  runSummary: () => Promise<void>;
}
