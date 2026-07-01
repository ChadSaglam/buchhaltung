"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import {
  Rocket, X, CheckCircle2, Circle, ArrowRight,
  ScanLine, FileText, Bot, ListChecks, type LucideIcon,
} from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Dismissible getting-started checklist for new tenants.
 *
 * Reads real system signals to decide which onboarding steps are done, shows a
 * progress bar, and hides itself automatically once every step is complete.
 * The user can also dismiss it manually; the choice is persisted per browser
 * so it doesn't reappear on every visit.
 */
const DISMISS_KEY = "getting-started-dismissed";

interface Step {
  id: string;
  label: string;
  desc: string;
  href: string;
  icon: LucideIcon;
  done: boolean;
}

export function GettingStarted() {
  const [visible, setVisible] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const dismissed = typeof window !== "undefined" && localStorage.getItem(DISMISS_KEY) === "true";

    (async () => {
      const [info, bookings, scanner] = await Promise.all([
        api.get("/api/classify/info").then((r) => r.data).catch(() => null),
        api.get("/api/bookings/stats").then((r) => r.data).catch(() => null),
        api.get("/api/scanner/vision-status").then((r) => r.data).catch(() => null),
      ]);

      const hasBookings = (bookings?.total_count ?? 0) > 0;
      const hasModel = !!info?.has_model;
      const hasMemory = (info?.memory_count ?? 0) > 0;
      const ollamaOk = !!scanner?.ok;

      const s: Step[] = [
        { id: "ollama", label: "AI-Dienst verbinden", desc: "Ollama starten für Scanner & Assistent", href: "/dashboard/scanner", icon: Bot, done: ollamaOk },
        { id: "import", label: "Erste Buchungen erfassen", desc: "Kontoauszug hochladen oder Beleg scannen", href: "/dashboard/kontoauszug", icon: FileText, done: hasBookings },
        { id: "scan", label: "Beleg scannen", desc: "Rechnung fotografieren → AI-Kontierung", href: "/dashboard/scanner", icon: ScanLine, done: hasMemory },
        { id: "train", label: "Modell trainieren", desc: "Automatische Kontierung aktivieren", href: "/dashboard/modell", icon: ListChecks, done: hasModel },
      ];
      setSteps(s);

      const allDone = s.every((x) => x.done);
      setVisible(!dismissed && !allDone);
      setLoading(false);
    })();
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, "true");
    setVisible(false);
  };

  if (loading || !visible) return null;

  const doneCount = steps.filter((s) => s.done).length;
  const progress = steps.length ? (doneCount / steps.length) * 100 : 0;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, height: 0, marginBottom: 0 }}
        transition={{ duration: 0.3 }}
        className="relative overflow-hidden rounded-xl border border-brand-500/25 bg-gradient-to-br from-brand-500/8 to-transparent p-5"
      >
        <button
          onClick={dismiss}
          aria-label="Ausblenden"
          className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="mb-4 flex items-start gap-3.5 pr-8">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-500/15 text-brand-600 dark:text-brand-300">
            <Rocket className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-base font-bold text-foreground">Erste Schritte</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {doneCount} von {steps.length} erledigt — richte deine Buchhaltung in wenigen Schritten ein.
            </p>
          </div>
        </div>

        <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-muted">
          <motion.div
            className="h-full rounded-full bg-primary"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {steps.map((step) => (
            <Link
              key={step.id}
              href={step.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg border p-3 transition-colors",
                step.done
                  ? "border-success/25 bg-success/5"
                  : "border-border bg-card hover:border-border-strong hover:bg-accent"
              )}
            >
              {step.done ? (
                <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />
              ) : (
                <Circle className="h-5 w-5 shrink-0 text-muted-foreground/40" />
              )}
              <div className="min-w-0 flex-1">
                <p className={cn("text-sm font-medium", step.done ? "text-muted-foreground line-through" : "text-foreground")}>
                  {step.label}
                </p>
                <p className="truncate text-xs text-muted-foreground">{step.desc}</p>
              </div>
              {!step.done && (
                <ArrowRight className="h-4 w-4 shrink-0 -translate-x-1 text-muted-foreground opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
              )}
            </Link>
          ))}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
