"use client";
import { motion } from "motion/react";
import { PageTransition } from "@/components/layout/PageTransition";
import { MetricCardSkeleton } from "@/components/shared/LoadingSkeleton";
import { useApi } from "@/hooks/useApi";
import Link from "next/link";

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
  by_source: Record<string, unknown>;
}

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export default function DashboardPage() {
  const { data: info, isLoading: infoLoading } = useApi<ClassifierInfo>("/api/classify/info");
  const { data: bookingStats, isLoading: bookingsLoading } = useApi<BookingStats>("/api/bookings/stats");
  const isLoading = infoLoading || bookingsLoading;

  const metrics = [
    { label: "ML-Modell", value: info ? `${Math.round(info.model_accuracy * 100)}%` : "–", sub: "Genauigkeit", color: "bg-brand-600", icon: "🤖" },
    { label: "Gedächtnis", value: info?.memory_count ?? "–", sub: "Einträge", color: "bg-success", icon: "🧠" },
    { label: "Korrekturen", value: info?.corrections_count ?? "–", sub: "Gesamt", color: "bg-warning", icon: "✏️" },
    { label: "Buchungen", value: bookingStats?.total_count ?? "–", sub: "In Datenbank", color: "bg-destructive", icon: "📚" },
  ];


  const actions = [
    { title: "Kontoauszug", desc: "UBS PDF hochladen → automatisch kontieren → Export", href: "/dashboard/kontoauszug", icon: "📄" },
    { title: "Rechnung Scanner", desc: "Quittung fotografieren → AI erkennt Daten → Buchung", href: "/dashboard/scanner", icon: "📸" },
    { title: "Kontenplan & Training", desc: "Kontenplan bearbeiten, Modell trainieren", href: "/dashboard/kontenplan", icon: "⚙️" },
    { title: "Modell Manager", desc: "ML-Modell testen, Gedächtnis verwalten", href: "/dashboard/modell", icon: "🧠" },
  ];

  return (
    <PageTransition>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Selbstlernende Schweizer Buchhaltung
          </p>
        </div>

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => <MetricCardSkeleton key={i} />)
            : metrics.map((m) => (
                <motion.div key={m.label} variants={item}>
                  <div className="bg-card border border-border rounded-xl p-5 relative overflow-hidden">
                    <div className={`absolute top-0 left-0 w-full h-[2px] ${m.color}`} />
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          {m.label}
                        </p>
                        <p className="text-3xl font-bold text-foreground mt-1">{m.value}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">{m.sub}</p>
                      </div>
                      <span className="text-2xl opacity-60">{m.icon}</span>
                    </div>
                  </div>
                </motion.div>
              ))}
        </motion.div>

        <div>
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">
            Schnellzugriff
          </h2>
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 sm:grid-cols-2 gap-4"
          >
            {actions.map((action) => (
              <motion.div key={action.title} variants={item}>
                <Link href={action.href}>
                  <div className="bg-card border border-border rounded-xl p-6 hover:bg-muted hover:border-brand-200 transition-all duration-200 cursor-pointer group">
                    <div className="flex items-start gap-4">
                      <span className="text-2xl group-hover:scale-110 transition-transform">{action.icon}</span>
                      <div>
                        <h3 className="font-semibold text-foreground">{action.title}</h3>
                        <p className="text-sm text-muted-foreground mt-1">{action.desc}</p>
                      </div>
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </PageTransition>
  );
}
