"use client";

import { motion } from "motion/react";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import { SystemChecklist } from "@/components/shared/SystemChecklist";
import { useApi } from "@/hooks/useApi";
import Link from "next/link";
import {
  Bot, Brain, Pencil, BookOpen, FileText,
  ScanLine, Settings, Cpu, ArrowRight
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ClassifierInfo {
  has_model: boolean;
  model_accuracy: number;
  train_accuracy: number;
  total_samples: number;
  classes: number;
  memory_count: number;
  corrections_count: number;
}

interface BookingStats {
  total_count: number;
  total_amount: number;
  by_source: Record<string, number>;
}

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

const METRICS = [
  { key: "accuracy", label: "ML-Modell", sub: "Genauigkeit", icon: Bot, color: "text-brand-600", bg: "bg-brand-50" },
  { key: "memory", label: "Gedächtnis", sub: "Einträge", icon: Brain, color: "text-emerald-600", bg: "bg-emerald-50" },
  { key: "corrections", label: "Korrekturen", sub: "Gesamt", icon: Pencil, color: "text-amber-600", bg: "bg-amber-50" },
  { key: "bookings", label: "Buchungen", sub: "In Datenbank", icon: BookOpen, color: "text-rose-600", bg: "bg-rose-50" },
] as const;

const ACTIONS = [
  { title: "Kontoauszug", desc: "PDF hochladen & automatisch kontieren", href: "/dashboard/kontoauszug", icon: FileText, color: "text-blue-600" },
  { title: "Rechnung Scanner", desc: "Quittung fotografieren → AI Buchung", href: "/dashboard/scanner", icon: ScanLine, color: "text-violet-600" },
  { title: "Kontenplan", desc: "Kontenplan bearbeiten & Modell trainieren", href: "/dashboard/kontenplan", icon: Settings, color: "text-emerald-600" },
  { title: "Modell Manager", desc: "ML-Modell testen & Gedächtnis verwalten", href: "/dashboard/modell", icon: Cpu, color: "text-amber-600" },
];

export default function DashboardPage() {
  const { data: info, isLoading: infoLoading } = useApi<ClassifierInfo>("/api/classify/info");
  const { data: bookingStats, isLoading: bookingsLoading } = useApi<BookingStats>("/api/bookings/stats");
  const isLoading = infoLoading || bookingsLoading;

  const metricValues: Record<string, string | number> = {
    accuracy: info ? `${Math.round(info.model_accuracy * 100)}%` : "–",
    memory: info?.memory_count ?? "–",
    corrections: info?.corrections_count ?? "–",
    bookings: bookingStats?.total_count ?? "–",
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Selbstlernende Schweizer Buchhaltung — Übersicht
        </p>
      </div>

      {/* Two-column: metrics + checklist */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6">
        {/* Left: Metrics + Actions */}
        <div className="space-y-8">
          <motion.div variants={container} initial="hidden" animate="show" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => <MetricCardSkeleton key={i} />)
              : METRICS.map((m) => (
                  <motion.div
                    key={m.key}
                    variants={item}
                    className="group relative rounded-xl border border-border bg-card p-5 transition-shadow hover:shadow-lg hover:shadow-black/5"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{m.label}</p>
                        <p className="mt-2 text-2xl font-bold text-foreground">{metricValues[m.key]}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{m.sub}</p>
                      </div>
                      <div className={cn("rounded-lg p-2.5", m.bg)}>
                        <m.icon className={cn("h-5 w-5", m.color)} />
                      </div>
                    </div>
                  </motion.div>
                ))}
          </motion.div>

          <div>
            <h2 className="mb-4 text-lg font-semibold text-foreground">Schnellzugriff</h2>
            <motion.div variants={container} initial="hidden" animate="show" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {ACTIONS.map((action) => (
                <motion.div key={action.href} variants={item}>
                  <Link
                    href={action.href}
                    className="group flex items-start gap-4 rounded-xl border border-border bg-card p-5 transition-all hover:border-brand-200 hover:shadow-lg hover:shadow-black/5"
                  >
                    <div className="rounded-lg bg-accent p-2.5">
                      <action.icon className={cn("h-5 w-5", action.color)} />
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-foreground group-hover:text-brand-600 transition-colors">{action.title}</p>
                      <p className="mt-0.5 text-sm text-muted-foreground">{action.desc}</p>
                    </div>
                    <ArrowRight className="mt-1 h-4 w-4 text-muted-foreground opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                  </Link>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </div>

        {/* Right: System checklist */}
        <div className="lg:sticky lg:top-8 self-start">
          <SystemChecklist />
        </div>
      </div>
    </div>
  );
}
