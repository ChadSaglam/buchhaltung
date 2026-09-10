import { cn } from "@/lib/utils";
import { TABS } from "../helpers";
import type { TabId } from "../types";

export function SettingsTabs({ activeTab, onSelect }: { activeTab: TabId; onSelect: (id: TabId) => void }) {
  return (
    <nav className="flex md:flex-col gap-1 md:w-56 shrink-0">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onSelect(tab.id)}
          className={cn(
            "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all text-left",
            activeTab === tab.id
              ? "bg-brand-500/12 text-brand-600 dark:text-brand-300"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          )}
        >
          <tab.icon className="h-4 w-4" />
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
