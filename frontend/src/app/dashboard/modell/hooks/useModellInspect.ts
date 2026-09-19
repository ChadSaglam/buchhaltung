import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { filterMemory } from "../helpers";
import type { ClassifyResult, InspectTab, MemoryEntry, TrainingData } from "../types";

/**
 * B-58: the Gedächtnis and Top-Konten tabs used to fetch in a `useEffect` into
 * local state — no loading state, no error state, and a failed request left the
 * previous tab's rows on screen. Both are SWR readers now, keyed on `null`
 * until their tab is open, so nothing is fetched before it is looked at.
 */
export function useModellInspect() {
  const [activeTab, setActiveTab] = useState<InspectTab>("test");
  const [testInput, setTestInput] = useState("");
  const [testResult, setTestResult] = useState<ClassifyResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [memoryFilter, setMemoryFilter] = useState("");

  const memory = useApi<{ entries: MemoryEntry[] }>(activeTab === "memory" ? "/api/classify/memory" : null);
  const top = useApi<TrainingData[]>(activeTab === "top" ? "/api/classify/top-classes" : null);

  const handleTest = async () => {
    if (!testInput.trim()) return;
    setTestLoading(true);
    setTestResult(null);
    try {
      const res = await api.post("/api/classify/predict", { beschreibung: testInput, betrag: 100 });
      setTestResult(res.data);
    } catch {
      toast.error("Klassifizierung fehlgeschlagen");
    } finally {
      setTestLoading(false);
    }
  };

  const memoryEntries = memory.data?.entries ?? [];
  const topClasses = top.data ?? [];

  return {
    activeTab,
    setActiveTab,
    testInput,
    setTestInput,
    testResult,
    testLoading,
    handleTest,
    memoryEntries,
    memoryFilter,
    setMemoryFilter,
    filteredMemory: filterMemory(memoryEntries, memoryFilter),
    memoryLoading: memory.isLoading,
    memoryError: memory.error,
    retryMemory: () => memory.mutate(),
    topClasses,
    topLoading: top.isLoading,
    topError: top.error,
    retryTop: () => top.mutate(),
  };
}
