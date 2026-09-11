import { BookOpen, Plus, Search, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";
import { t } from "@/lib/i18n";
import type { Konto } from "../types";

interface Props {
  konten: Konto[];
  search: string;
  onUpdate: (idx: number, field: keyof Konto, value: string) => void;
  onRemove: (idx: number) => void;
  onAdd: () => void;
}

const INPUT = "w-full bg-transparent text-foreground focus:outline-none focus:ring-1 focus:ring-ring/30 rounded px-1 py-0.5";

export function KontenTable({ konten, search, onUpdate, onRemove, onAdd }: Props) {
  const q = search.toLowerCase();
  const filtered = konten.filter((k) => !search || k.konto.includes(search) || k.bezeichnung.toLowerCase().includes(q));

  if (konten.length === 0) {
    return (
      <EmptyState
        icon={BookOpen}
        title={t("empty.kontenplan.title")}
        description={t("empty.kontenplan.desc")}
        action={
          <Button variant="outline" onClick={onAdd} icon={<Plus className="h-4 w-4" aria-hidden="true" />}>
            {t("kontenplan.add")}
          </Button>
        }
      />
    );
  }
  if (filtered.length === 0) {
    return <EmptyState icon={Search} title={t("empty.kontenplan.search")} description={t("empty.kontenplan.search_desc")} />;
  }

  return (
    <Card>
      <div className="overflow-hidden">
        <table className="w-full text-sm" aria-label="Kontenplan">
          <thead>
            <tr className="bg-muted border-b border-border">
              <th scope="col" className="text-left px-4 py-3 font-medium text-muted-foreground w-32">Konto-Nr.</th>
              <th scope="col" className="text-left px-4 py-3 font-medium text-muted-foreground">Bezeichnung</th>
              <th scope="col" className="w-12"><span className="sr-only">Aktionen</span></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((k) => {
              const idx = konten.indexOf(k);
              return (
                <tr key={idx} className="border-b border-border last:border-0 hover:bg-accent transition-colors">
                  <td className="px-4 py-2">
                    <input
                      aria-label={`Konto-Nr. Zeile ${idx + 1}`}
                      value={k.konto}
                      onChange={(e) => onUpdate(idx, "konto", e.target.value)}
                      className={`${INPUT} font-mono`}
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      aria-label={`Bezeichnung Zeile ${idx + 1}`}
                      value={k.bezeichnung}
                      onChange={(e) => onUpdate(idx, "bezeichnung", e.target.value)}
                      className={INPUT}
                    />
                  </td>
                  <td className="px-2">
                    <button
                      type="button"
                      onClick={() => onRemove(idx)}
                      className="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                      aria-label={`Konto ${k.konto || idx + 1} löschen`}
                    >
                      <X className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
