"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import {
  Rocket, X, CheckCircle2, Circle, ArrowRight,
  ScanLine, FileText, Bot, ListChecks, type LucideIcon,
} from "lucide-react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useBookingStats, useClassifierInfo, useVisionStatus } from "@/hooks/useSystemData";
import { cn } from "@/lib/utils";

/**
 * The first run (B-20).
 *
 * Reads real system signals to decide which step is done, shows a progress bar,
 * and hides itself once everything is. Dismissal is per browser.
 *
 * The order is the point. `docs/IA-2026-09-14.md` rule 3 is "no settings before
 * value: first run, drop a file → see a result", and this checklist used to open
 * with "start Ollama" — a technical prerequisite that produces nothing a new
 * user can see, asked before they have any reason to care. Reading a receipt is
 * now step one, and the AI service is last, where it belongs: it makes the
 * reading better, it is not what makes it work (a Swiss QR bill is decoded
 * exactly, with no model involved at all).
 *
 * Step one also carries the answer to the most ordinary first-run problem —
 * they do not have a Swiss invoice on the laptop they signed up on. The sample
 * is a real, scannable QR-Rechnung marked "Beispiel", so the first thing they
 * see is the exact behaviour, not a demo of it.
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
  const [dismissed, setDismissed] = useState<boolean | null>(null);
  const info = useClassifierInfo();
  const bookings = useBookingStats();
  const scanner = useVisionStatus();

  useEffect(() => {
    setDismissed(localStorage.getItem(DISMISS_KEY) === "true");
  }, []);

  const loading = dismissed === null || info.isLoading || bookings.isLoading || scanner.isLoading;
  const hasBookings = (bookings.data?.total_count ?? 0) > 0;
  const hasModel = !!info.data?.has_model;
  const hasMemory = (info.data?.memory_count ?? 0) > 0;
  const ollamaOk = !!scanner.data?.ok;

  const steps: Step[] = [
    { id: "beleg", label: "Ersten Beleg einlesen", desc: "Rechnung hierher ziehen — der QR-Code wird exakt gelesen", href: "/dashboard/belege", icon: ScanLine, done: hasMemory || hasBookings },
    { id: "bank", label: "Kontoauszug hochladen", desc: "Damit die Zahlungen zu den Belegen passen", href: "/dashboard/bank", icon: FileText, done: hasBookings },
    { id: "train", label: "Kontierung lernen lassen", desc: "Aus Ihren Korrekturen, sobald ein paar Belege da sind", href: "/dashboard/modell", icon: ListChecks, done: hasModel },
    { id: "ollama", label: "AI-Dienst verbinden", desc: "Optional — verbessert das Lesen von Belegen ohne QR-Code", href: "/dashboard/belege/scanner", icon: Bot, done: ollamaOk },
  ];
  const visible = !dismissed && !steps.every((x) => x.done);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, "true");
    setDismissed(true);
  };

  /** The endpoint needs the bearer token, so a plain <a href> would 401. */
  const beispielHolen = async () => {
    try {
      const res = await api.get("/api/onboarding/beispiel-rechnung.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "Beispiel-Rechnung.pdf";
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(errorMessage(e));
    }
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

        <p className="mb-3 text-xs text-muted-foreground">
          Keine Rechnung zur Hand?{" "}
          <button type="button" onClick={beispielHolen} className="font-medium text-link hover:underline">
            Beispielrechnung herunterladen
          </button>{" "}
          und oben hineinziehen — sie trägt einen Beispiel-Vermerk und ist keine echte Forderung.
        </p>

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
