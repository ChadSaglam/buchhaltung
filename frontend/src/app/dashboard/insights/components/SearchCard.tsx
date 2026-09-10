import { Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EXAMPLES } from "../helpers";

export function SearchCard({ query, setQuery, activeFilters, resultCount }: {
  query: string;
  setQuery: (q: string) => void;
  activeFilters: string[];
  resultCount: number;
}) {
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2.5 rounded-lg border border-border bg-surface px-3 focus-within:border-border-strong focus-within:ring-2 focus-within:ring-ring/30">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="z. B. Ausgaben über 500 im Juni  ·  Migros Lebensmittel  ·  Konto 6500"
            className="h-11 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          {query && (
            <button onClick={() => setQuery("")} className="text-xs text-muted-foreground hover:text-foreground">
              Löschen
            </button>
          )}
        </div>

        {!query && (
          <div className="flex flex-wrap gap-1.5">
            <span className="text-xs text-muted-foreground">Beispiele:</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => setQuery(ex)}
                className="rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
              >
                {ex}
              </button>
            ))}
          </div>
        )}

        {query && activeFilters.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {activeFilters.map((f) => (
              <Badge key={f} tone="brand">{f}</Badge>
            ))}
            <span className="ml-1 text-xs text-muted-foreground">{resultCount} Treffer</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
