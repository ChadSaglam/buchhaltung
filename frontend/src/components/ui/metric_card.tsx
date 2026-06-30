"use client";
import { motion } from "motion/react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

type Accent = "brand" | "success" | "warning" | "danger" | "info" | "neutral";

const accents: Record<Accent, { icon: string; ring: string }> = {
  brand: { icon: "text-brand-600 dark:text-brand-300 bg-brand-500/12", ring: "before:bg-brand-500" },
  success: { icon: "text-success bg-success/12", ring: "before:bg-success" },
  warning: { icon: "text-warning bg-warning/15", ring: "before:bg-warning" },
  danger: { icon: "text-destructive bg-destructive/12", ring: "before:bg-destructive" },
  info: { icon: "text-info bg-info/12", ring: "before:bg-info" },
  neutral: { icon: "text-muted-foreground bg-muted", ring: "before:bg-border-strong" },
};

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  accent?: Accent;
  trend?: { value: string; direction: "up" | "down" };
}

export function MetricCard({ title, value, subtitle, icon, accent = "brand", trend }: MetricCardProps) {
  const a = accents[accent];
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
      className={cn(
        "group relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-sm",
        "before:absolute before:left-0 before:top-0 before:h-full before:w-1 before:content-['']",
        a.ring
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
          <p className="mt-2 text-2xl font-bold tabular-nums text-foreground">{value}</p>
          {subtitle && <p className="mt-0.5 truncate text-xs text-muted-foreground">{subtitle}</p>}
          {trend && (
            <span
              className={cn(
                "mt-2 inline-flex items-center gap-1 text-xs font-medium",
                trend.direction === "up" ? "text-success" : "text-destructive"
              )}
            >
              {trend.direction === "up" ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {trend.value}
            </span>
          )}
        </div>
        {icon && (
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg [&_svg]:h-5 [&_svg]:w-5", a.icon)}>
            {icon}
          </div>
        )}
      </div>
    </motion.div>
  );
}
