"use client";

import { motion, AnimatePresence } from "motion/react";
import { Loader2, CheckCircle2, XCircle, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PipelineStep {
  icon: string;
  label: string;
  status: "active" | "done" | "failed" | "pending";
  model?: string;
  provider?: string;
  source?: string;
  confidence?: number;
}

interface ProcessingOverlayProps {
  steps: PipelineStep[];
  fileName: string;
  elapsed: number;
  isCloud: boolean;
}

function StepIcon({ status }: { status: PipelineStep["status"] }) {
  switch (status) {
    case "done":
      return <CheckCircle2 className="h-4 w-4 text-success" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-destructive" />;
    case "active":
      return <Loader2 className="h-4 w-4 animate-spin text-brand-600 dark:text-brand-300" />;
    default:
      return <Circle className="h-4 w-4 text-muted-foreground/30" />;
  }
}

export function ProcessingOverlay({ steps, fileName, elapsed, isCloud }: ProcessingOverlayProps) {
  const doneCount = steps.filter((s) => s.status === "done").length;
  const progress = steps.length > 0 ? Math.min((doneCount / Math.max(steps.length, 3)) * 100, 95) : 5;
  const activeStep = [...steps].reverse().find((s) => s.status === "active");

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="rounded-2xl border border-brand-500/25 bg-brand-500/6 p-6 sm:p-8"
    >
      <div className="mb-5 flex items-center gap-3">
        <Loader2 className="h-6 w-6 animate-spin text-brand-600 dark:text-brand-300" />
        <div>
          <p className="text-base font-semibold text-foreground">
            {activeStep ? `${activeStep.icon} ${activeStep.label}` : "Verarbeitung läuft..."}
          </p>
          <p className="text-xs text-muted-foreground">{fileName}</p>
        </div>
      </div>

      <div className="mb-5">
        <div className="overflow-hidden rounded-full bg-brand-500/15">
          <motion.div
            className="h-2 rounded-full bg-brand-600 dark:bg-brand-400"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.4 }}
          />
        </div>
        <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
          <span className="tabular-nums">{elapsed}s</span>
          <span>{isCloud ? "Cloud-Modell" : "Lokales Modell"}</span>
        </div>
      </div>

      <div className="space-y-1">
        <AnimatePresence mode="popLayout">
          {steps.map((step, i) => (
            <motion.div
              key={`${i}-${step.label}-${step.model ?? ""}`}
              initial={{ opacity: 0, x: -8, height: 0 }}
              animate={{ opacity: 1, x: 0, height: "auto" }}
              transition={{ duration: 0.2 }}
              className={cn(
                "rounded-lg px-3 py-2 text-sm",
                step.status === "active" && "bg-brand-500/12",
                step.status === "failed" && "bg-destructive/8"
              )}
            >
              <div className="flex items-center gap-3">
                <StepIcon status={step.status} />
                <span className="text-sm">{step.icon}</span>
                <span
                  className={cn(
                    "flex-1",
                    step.status === "done" && "text-success",
                    step.status === "failed" && "text-destructive",
                    step.status === "active" && "font-medium text-brand-600 dark:text-brand-300",
                    step.status === "pending" && "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
                {step.model && (
                  <span className="font-mono text-[11px] text-muted-foreground">{step.model}</span>
                )}
              </div>

              {(step.provider || step.source || typeof step.confidence === "number") && (
                <div className="mt-1 pl-10 text-[11px] text-muted-foreground">
                  {[step.provider, step.source, typeof step.confidence === "number" ? `${Math.round(step.confidence * 100)}%` : null]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
