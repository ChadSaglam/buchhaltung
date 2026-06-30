"use client";

import { motion } from "motion/react";
import Link from "next/link";
import {
  Bot, Brain, Pencil, BookOpen, FileText,
  ScanLine, Settings, Cpu, ArrowRight,
} from "lucide-react";
import { MetricCard } from "@/components/ui/metric_card";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import { SystemChecklist } from "@/components/shared/SystemChecklist";
import { useApi } from "@/hooks/useApi";
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
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const } },
};

const ACTIONS = [
  { title: "Kontoauszug", desc: "PDF hochladen & automatisch kontieren", href: "/dashboard/kontoauszug", icon: FileText, tint: "text-info bg-info/12" },
  { title: "Rechnung Scanner", desc: "Quittung fotografieren → AI Buchung", href: "/dashboard/scanner", icon: ScanLine, tint: "text-brand-600 dark:text-brand-300 bg-brand-500/12" },
  { title: "Kontenplan", desc: "Kontenplan bearbeiten & Modell trainieren", href: "/dashboard/kontenplan", icon: Settings, tint: "text-success bg-success/12" },
  { title: "Modell Manager", desc: "ML-Modell testen & Gedächtnis verwalten", href: "/dashboard/modell", icon: Cpu, tint: "text-warning bg-warning/15" },
];

export default function DashboardPage() {
  const { data: info, isLoading: infoLoading } = useApi<ClassifierInfo>("/api/classify/info");
  const { data: bookingStats, isLoading: bookingsLoading } = useApi<BookingStats>("/api/bookings/stats");
  const isLoading = infoLoading || bookingsLoading;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Selbstlernende Schweizer Buchhaltung — Übersicht
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left: Metrics + Actions */}
        <div className="space-y-8">
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2"
          >
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <MetricCardSkeleton key={i} />)
            ) : (
              <>
                <motion.div variants={item}>
                  <MetricCard
                    title="ML-Modell"
                    value={info ? `${Math.round(info.model_accuracy * 100)}%` : "–"}
                    subtitle="Genauigkeit"
                    accent="brand"
                    icon={<Bot />}
                  />
                </motion.div>
                <motion.div variants={item}>
                  <MetricCard
                    title="Gedächtnis"
                    value={info?.memory_count ?? "–"}
                    subtitle="Einträge"
                    accent="success"
                    icon={<Brain />}
                  />
                </motion.div>
                <motion.div variants={item}>
                  <MetricCard
                    title="Korrekturen"
                    value={info?.corrections_count ?? "–"}
                    subtitle="Gesamt"
                    accent="warning"
                    icon={<Pencil />}
                  />
                </motion.div>
                <motion.div variants={item}>
                  <MetricCard
                    title="Buchungen"
                    value={bookingStats?.total_count ?? "–"}
                    subtitle="In Datenbank"
                    accent="danger"
                    icon={<BookOpen />}
                  />
                </motion.div>
              </>
            )}
          </motion.div>

          <div>
            <h2 className="mb-4 text-base font-semibold text-foreground">Schnellzugriff</h2>
            <motion.div
              variants={container}
              initial="hidden"
              animate="show"
              className="grid grid-cols-1 gap-4 sm:grid-cols-2"
            >
              {ACTIONS.map((action) => (
                <motion.div key={action.href} variants={item}>
                  <Link
                    href={action.href}
                    className="group flex items-start gap-4 rounded-xl border border-border bg-card p-5 shadow-sm transition-[transform,box-shadow,border-color] hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md"
                  >
                    <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-lg [&_svg]:h-5 [&_svg]:w-5", action.tint)}>
                      <action.icon />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-foreground transition-colors group-hover:text-brand-600 dark:group-hover:text-brand-300">
                        {action.title}
                      </p>
                      <p className="mt-0.5 text-sm text-muted-foreground">{action.desc}</p>
                    </div>
                    <ArrowRight className="mt-1 h-4 w-4 -translate-x-2 text-muted-foreground opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
                  </Link>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </div>

        {/* Right: System checklist */}
        <div className="self-start lg:sticky lg:top-[calc(var(--topbar-height)+1.5rem)]">
          <SystemChecklist />
        </div>
      </div>
    </div>
  );
}
