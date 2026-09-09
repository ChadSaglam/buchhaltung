import { Brain, BarChart3, TestTube, RotateCcw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { InspectTab, ModelInfo } from "../types";
import type { useModellInspect } from "../hooks/useModellInspect";
import { TestTab } from "./TestTab";
import { TopClassesTab } from "./TopClassesTab";
import { MemoryTab } from "./MemoryTab";
import { RetrainTab } from "./RetrainTab";

interface InspectTabsProps {
  info: ModelInfo | null;
  training: boolean;
  handleTrain: () => void;
  inspect: ReturnType<typeof useModellInspect>;
}

export function InspectTabs({ info, training, handleTrain, inspect }: InspectTabsProps) {
  const {
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
  } = inspect;

  return (
    <Card>
      <div className="flex border-b border-border">
        {[
          { key: "test", icon: TestTube, label: "Testen" },
          { key: "top", icon: BarChart3, label: "Top-Konten" },
          { key: "memory", icon: Brain, label: "Gedächtnis" },
          { key: "retrain", icon: RotateCcw, label: "Neu trainieren" },
        ].map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as InspectTab)}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-3.5 text-sm font-medium transition-all",
              activeTab === key
                ? "text-brand-600 dark:text-brand-300 border-b-2 border-brand-600 dark:border-brand-300 bg-brand-500/6"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      <CardContent className="pt-5">
        {/* Test Tab */}
        {activeTab === "test" && (
          <TestTab
            testInput={testInput}
            setTestInput={setTestInput}
            testResult={testResult}
            testLoading={testLoading}
            handleTest={handleTest}
          />
        )}

        {/* Top Classes Tab */}
        {activeTab === "top" && <TopClassesTab topClasses={topClasses} />}

        {/* Memory Tab */}
        {activeTab === "memory" && (
          <MemoryTab
            memoryEntries={memoryEntries}
            filteredMemory={filteredMemory}
            memoryFilter={memoryFilter}
            setMemoryFilter={setMemoryFilter}
          />
        )}

        {/* Retrain Tab */}
        {activeTab === "retrain" && (
          <RetrainTab info={info} training={training} handleTrain={handleTrain} />
        )}
      </CardContent>
    </Card>
  );
}
