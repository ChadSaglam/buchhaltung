"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import {
  CheckCircle2, XCircle, Server, Eye, Bot,
  Brain, BookOpen, ChevronRight, Loader2, RefreshCw
} from "lucide-react";
import { cn } from "@/lib/utils";
import api from "@/lib/api";

interface SystemStatus {
  ollama: boolean;
  vision: boolean;
  visionModel: string | null;
  mlModel: boolean;
  mlAccuracy: number;
  memoryCount: number;
  bookingCount: number;
}

interface CheckItem {
  label: string;
  ok: boolean;
  detail: string;
  icon: React.ElementType;
  color: string;
  href?: string;
}

function buildChecklist(s: SystemStatus): CheckItem[] {
  return [
    { label: "Ollama", ok: s.ollama, detail: s.ollama ? "Verbunden" : "Offline", icon: Server, color: "text-blue-600", href: undefined },
    { label: "Vision AI", ok: s.vision, detail: s.visionModel || "Kein Modell", icon: Eye, color: "text-violet-600", href: "/dashboard/scanner" },
    { label: "ML-Modell", ok: s.mlModel, detail: s.mlModel ? `${Math.round(s.mlAccuracy * 100)}%` : "Nicht trainiert", icon: Bot, color: "text-brand-600", href: "/dashboard/modell" },
    { label: "Gedächtnis", ok: s.memoryCount > 0, detail: `${s.memoryCount} Einträge`, icon: Brain, color: "text-emerald-600", href: "/dashboard/modell" },
    { label: "Buchungen", ok: s.bookingCount > 0, detail: `${s.bookingCount} gespeichert`, icon: BookOpen, color: "text-rose-600", href: "/dashboard/kontoauszug" },
  ];
}

export function SystemChecklist() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const [scanner, classify, bookings] = await Promise.all([
        api.get("/api/scanner/vision-status").catch(() => ({ data: { ok: false } })),
        api.get("/api/classify/info").catch(() => ({ data: { has_model: false, model_accuracy: 0, memory_count: 0 } })),
        api.get("/api/bookings/stats").catch(() => ({ data: { total_count: 0 } })),
      ]);
      setStatus({
        ollama: scanner.data.ok ?? false,
        vision: !!scanner.data.best_vision,
        visionModel: scanner.data.best_vision ?? null,
        mlModel: classify.data.has_model ?? false,
        mlAccuracy: classify.data.model_accuracy ?? 0,
        memoryCount: classify.data.memory_count ?? 0,
        bookingCount: bookings.data.total_count ?? 0,
      });
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const checklist = status ? buildChecklist(status) : [];
  const okCount = checklist.filter((c) => c.ok).length;
  const total = checklist.length;
  const allGood = okCount === total;
  const progress = total > 0 ? (okCount / total) * 100 : 0;

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 space-y-3 animate-pulse">
        <div className="h-4 w-32 rounded bg-muted" />
        <div className="h-2 rounded-full bg-muted" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-muted" />
            <div className="h-3 w-24 rounded bg-muted" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 pb-3">
        <div>
          <p className="text-sm font-semibold text-foreground">Systemstatus</p>
          <p className="text-xs text-muted-foreground">
            {allGood ? "Alle Systeme betriebsbereit" : `${okCount}/${total} aktiv`}
          </p>
        </div>
        <button
          onClick={() => fetchStatus(true)}
          disabled={refreshing}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          title="Aktualisieren"
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
        </button>
      </div>

      {/* Progress bar */}
      <div className="px-4 pb-3">
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <motion.div
            className={cn("h-full rounded-full", allGood ? "bg-emerald-500" : "bg-amber-500")}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Items */}
      <div className="px-2 pb-2">
        {checklist.map((check, i) => {
          const Wrapper = check.href ? "a" : "div";
          return (
            <motion.div
              key={check.label}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06 }}
            >
              <Wrapper
                {...(check.href ? { href: check.href } : {})}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors",
                  check.href && "hover:bg-accent cursor-pointer"
                )}
              >
                <div className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                  check.ok ? "bg-emerald-50" : "bg-red-50"
                )}>
                  {check.ok ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{check.label}</p>
                  <p className={cn(
                    "text-xs truncate",
                    check.ok ? "text-emerald-600" : "text-red-500"
                  )}>
                    {check.detail}
                  </p>
                </div>
                {check.href && (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />
                )}
              </Wrapper>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
