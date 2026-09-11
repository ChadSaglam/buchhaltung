import useSWR from "swr";
import { api } from "@/lib/api";
import type { LernverlaufData } from "../types";

// One key, four requests: the page is only useful when all of them are in.
async function fetchAll(): Promise<LernverlaufData> {
  const [memory, corrections, stats, info] = await Promise.all([
    api.get("/api/classify/memory"),
    api.get("/api/classify/corrections"),
    api.get("/api/stats/learning"),
    api.get("/api/classify/info"),
  ]);
  return {
    memory: memory.data.entries || [],
    corrections: corrections.data.corrections || [],
    stats: stats.data,
    info: info.data,
  };
}

export function useLernverlauf() {
  const { data, error, isLoading, mutate } = useSWR<LernverlaufData>("lernverlauf", fetchAll, {
    revalidateOnFocus: false,
  });
  return { data, error, loading: isLoading, retry: () => mutate() };
}
