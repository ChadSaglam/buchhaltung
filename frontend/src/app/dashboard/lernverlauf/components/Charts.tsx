import { motion } from "motion/react";
import { BarChart3 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";
import { t } from "@/lib/i18n";
import type { ChartBar, LearningStats } from "../types";

function HBar({ data, title, colorClass }: { data: ChartBar[]; title: string; colorClass: string }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div>
      <h3 className="font-semibold text-foreground mb-3 text-sm">{title}</h3>
      {data.length === 0 ? (
        <p className="text-muted-foreground text-sm py-4">{t("empty.lernverlauf.charts")}</p>
      ) : (
        <ul className="space-y-2" aria-label={title}>
          {data.map((item, i) => (
            <li key={i} className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground w-16 text-right font-mono truncate">{item.label}</span>
              <div
                className="flex-1 bg-muted rounded-full h-5 overflow-hidden"
                role="meter"
                aria-label={item.label}
                aria-valuemin={0}
                aria-valuemax={max}
                aria-valuenow={item.count}
              >
                <div className={`h-full rounded-full ${colorClass} transition-all duration-500`} style={{ width: `${(item.count / max) * 100}%` }} />
              </div>
              <span className="text-xs text-muted-foreground w-8 text-right tabular-nums">{item.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** One histogram is keyed by account, another by source — flatten both to a label. */
function bars<K extends string>(rows: ({ count: number } & Record<K, string>)[] | undefined, key: K): ChartBar[] {
  return (rows ?? []).map((row) => ({ label: row[key] || "—", count: row.count }));
}

export function Charts({ stats }: { stats: LearningStats }) {
  const charts = [
    { data: bars(stats.memory_distribution, "account"), title: t("lernverlauf.memory_dist"), colorClass: "bg-brand-500" },
    { data: bars(stats.correction_distribution, "account"), title: t("lernverlauf.correction_dist"), colorClass: "bg-warning" },
    { data: bars(stats.source_distribution, "source"), title: t("lernverlauf.source_dist"), colorClass: "bg-success", span: true },
  ];
  if (charts.every((c) => c.data.length === 0)) {
    return <EmptyState icon={BarChart3} title={t("empty.lernverlauf.charts")} description={t("empty.lernverlauf.charts_desc")} />;
  }
  return (
    <div className="grid md:grid-cols-2 gap-6">
      {charts.map((chart, i) => (
        <motion.div
          key={chart.title}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: i * 0.07 }}
          className={chart.span ? "md:col-span-2" : ""}
        >
          <Card>
            <CardContent className="pt-5">
              <HBar data={chart.data} title={chart.title} colorClass={chart.colorClass} />
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}
