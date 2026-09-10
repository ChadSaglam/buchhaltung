import { useState } from "react";
import { aiSummary } from "@/lib/api";
import type { AiSummaryState } from "../types";

export function useAiSummary(): AiSummaryState {
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryFallback, setSummaryFallback] = useState(false);
  const [summarizing, setSummarizing] = useState(false);

  const runSummary = async () => {
    setSummarizing(true);
    setSummary(null);
    try {
      const res = await aiSummary();
      if (res.error || !res.content) {
        setSummaryFallback(true);
      } else {
        setSummary(res.content);
        setSummaryFallback(false);
      }
    } catch {
      setSummaryFallback(true);
    } finally {
      setSummarizing(false);
    }
  };

  return { summary, summaryFallback, summarizing, runSummary };
}
