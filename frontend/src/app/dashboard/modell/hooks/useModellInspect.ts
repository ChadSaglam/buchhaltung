import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { filterMemory } from "../helpers";
import type { ClassifyResult, InspectTab, MemoryEntry, TrainingData } from "../types";

export function useModellInspect() {
  const [activeTab, setActiveTab] = useState<InspectTab>("test");
  const [testInput, setTestInput] = useState("");
  const [testResult, setTestResult] = useState<ClassifyResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [memoryEntries, setMemoryEntries] = useState<MemoryEntry[]>([]);
  const [memoryFilter, setMemoryFilter] = useState("");
  const [topClasses, setTopClasses] = useState<TrainingData[]>([]);

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

  const fetchMemory = async () => {
    const res = await api.get("/api/classify/memory");
    setMemoryEntries(res.data.entries);
  };

  const fetchTopClasses = async () => {
    const res = await api.get("/api/classify/top-classes");
    setTopClasses(res.data);
  };

  useEffect(() => {
    if (activeTab === "memory") fetchMemory();
    if (activeTab === "top") fetchTopClasses();
  }, [activeTab]);

  const filteredMemory = filterMemory(memoryEntries, memoryFilter);

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
    filteredMemory,
    topClasses,
  };
}
