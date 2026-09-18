import { cn } from "@/lib/utils";

export function StatCard({
  icon,
  label,
  value,
  sub,
  valueClass = "text-foreground",
  title,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  valueClass?: string;
  /** What the number measures, when that is not obvious from the label (B-88). */
  title?: string;
}) {
  return (
    <div
      title={title}
      className="relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{label}</span>
      </div>
      <div className={cn("text-2xl font-extrabold tabular-nums", valueClass)}>{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{sub}</div>
    </div>
  );
}
