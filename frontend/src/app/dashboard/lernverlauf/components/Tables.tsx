import { motion } from "motion/react";
import { Brain, Pencil, ScanLine } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/shared/EmptyState";
import { t } from "@/lib/i18n";
import type { CorrectionEntry, MemoryEntry } from "../types";

const TH = "px-4 py-3 font-medium text-muted-foreground";
const ROW = "border-b border-border last:border-0 hover:bg-accent transition-colors";
const fade = (i: number) => ({
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  transition: { duration: 0.2, delay: Math.min(i * 0.03, 0.3) },
});

const scanAction = (
  <ButtonLink variant="outline" href="/dashboard/scanner" icon={<ScanLine className="h-4 w-4" aria-hidden="true" />}>
    {t("empty.lernverlauf.action")}
  </ButtonLink>
);

export function MemoryTable({ entries, search }: { entries: MemoryEntry[]; search: string }) {
  const rows = entries.filter((m) => !search || m.lookup_key.includes(search.toLowerCase()) || m.kt_soll.includes(search));
  if (entries.length === 0) {
    return <EmptyState icon={Brain} title={t("lernverlauf.memory_empty")} description={t("empty.lernverlauf.memory_desc")} action={scanAction} />;
  }
  if (rows.length === 0) return <EmptyState title={t("empty.insights.search")} description={t("empty.insights.search_desc")} />;
  return (
    <Card>
      <div className="overflow-hidden">
        <table className="w-full text-sm" aria-label={t("lernverlauf.memory_tab")}>
          <thead>
            <tr className="bg-muted border-b border-border text-left">
              <th scope="col" className={TH}>Beschreibung</th>
              <th scope="col" className={TH}>KtSoll</th>
              <th scope="col" className={TH}>KtHaben</th>
              <th scope="col" className={TH}>MwSt</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m, i) => (
              <motion.tr key={m.lookup_key} {...fade(i)} className={ROW}>
                <td className="px-4 py-2.5 text-foreground">{m.lookup_key}</td>
                <td className="px-4 py-2.5 font-mono text-brand-600 dark:text-brand-300">{m.kt_soll}</td>
                <td className="px-4 py-2.5 font-mono text-success">{m.kt_haben}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{m.mwst_code} {m.mwst_pct}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function CorrectionsTable({ entries, search }: { entries: CorrectionEntry[]; search: string }) {
  const rows = entries.filter((c) => !search || c.beschreibung.toLowerCase().includes(search.toLowerCase()));
  if (entries.length === 0) {
    return <EmptyState icon={Pencil} title={t("lernverlauf.corrections_empty")} description={t("empty.lernverlauf.corrections_desc")} action={scanAction} />;
  }
  if (rows.length === 0) return <EmptyState title={t("empty.insights.search")} description={t("empty.insights.search_desc")} />;
  return (
    <Card>
      <div className="overflow-hidden">
        <table className="w-full text-sm" aria-label={t("lernverlauf.corrections_tab")}>
          <thead>
            <tr className="bg-muted border-b border-border text-left">
              <th scope="col" className={TH}>Zeitpunkt</th>
              <th scope="col" className={TH}>Beschreibung</th>
              <th scope="col" className={TH}>Original → Korrigiert</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c, i) => (
              <motion.tr key={`${c.created_at}-${i}`} {...fade(i)} className={ROW}>
                <td className="px-4 py-2.5 text-muted-foreground text-xs tabular-nums">{c.created_at?.slice(0, 16).replace("T", " ") || "—"}</td>
                <td className="px-4 py-2.5 text-foreground">{c.beschreibung}</td>
                <td className="px-4 py-2.5">
                  <span className="text-destructive font-mono">{c.original_soll}</span>
                  <span className="text-muted-foreground mx-1.5" aria-hidden="true">→</span>
                  <span className="text-success font-mono">{c.corrected_soll}</span>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
