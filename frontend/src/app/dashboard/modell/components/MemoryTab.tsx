import { Brain, Search } from "lucide-react";
import type { MemoryEntry } from "../types";

interface MemoryTabProps {
  memoryEntries: MemoryEntry[];
  filteredMemory: MemoryEntry[];
  memoryFilter: string;
  setMemoryFilter: (value: string) => void;
}

export function MemoryTab({ memoryEntries, filteredMemory, memoryFilter, setMemoryFilter }: MemoryTabProps) {
  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={memoryFilter}
            onChange={(e) => setMemoryFilter(e.target.value)}
            placeholder="Gedächtnis durchsuchen…"
            className="w-full pl-9 pr-4 py-2 border border-input rounded-xl text-sm text-foreground bg-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 transition-all"
          />
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap tabular-nums">
          {filteredMemory.length} / {memoryEntries.length} Einträge
        </span>
      </div>
      {filteredMemory.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-border max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card">
              <tr className="bg-muted text-left border-b border-border">
                <th className="px-4 py-2.5 font-semibold text-muted-foreground">Beschreibung</th>
                <th className="px-4 py-2.5 font-semibold text-muted-foreground">KtSoll</th>
                <th className="px-4 py-2.5 font-semibold text-muted-foreground">KtHaben</th>
                <th className="px-4 py-2.5 font-semibold text-muted-foreground">MwSt</th>
              </tr>
            </thead>
            <tbody>
              {filteredMemory.map((entry) => (
                <tr key={entry.lookup_key} className="border-t border-border hover:bg-accent transition-colors">
                  <td className="px-4 py-2 text-foreground max-w-xs truncate">{entry.lookup_key}</td>
                  <td className="px-4 py-2 font-mono text-foreground">{entry.kt_soll}</td>
                  <td className="px-4 py-2 font-mono text-foreground">{entry.kt_haben}</td>
                  <td className="px-4 py-2 text-muted-foreground">{entry.mwst_code || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <Brain className="w-8 h-8 mb-2 opacity-40" />
          <p className="text-sm">{memoryEntries.length === 0 ? "Gedächtnis ist leer" : "Keine Treffer"}</p>
        </div>
      )}
    </div>
  );
}
