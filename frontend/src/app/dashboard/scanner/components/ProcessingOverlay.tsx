"use client";

import { motion, AnimatePresence } from "motion/react";
import { Loader2, CheckCircle2, XCircle, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PipelineStep {
  icon: string;
  label: string;
  status: "active" | "done" | "failed" | "pending";
  model?: string;
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
      return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "active":
      return <Loader2 className="h-4 w-4 text-brand-600 animate-spin" />;
    default:
      return <Circle className="h-4 w-4 text-muted-foreground/30" />;
  }
}

export function ProcessingOverlay({ steps, fileName, elapsed, isCloud }: ProcessingOverlayProps) {
  const doneCount = steps.filter((s) => s.status === "done").length;
  const progress = steps.length > 0 ? Math.min((doneCount / Math.max(steps.length, 3)) * 100, 95) : 5;
  const activeStep = steps.findLast((s) => s.status === "active");

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50 to-white p-6 sm:p-8"
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <Loader2 className="h-6 w-6 text-brand-600 animate-spin" />
        <div>
          <p className="text-base font-semibold text-foreground">
            {activeStep ? `${activeStep.icon} ${activeStep.label}` : "Verarbeitung läuft..."}
          </p>
          <p className="text-xs text-muted-foreground">{fileName}</p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-5">
        <div className="h-2 rounded-full bg-brand-100 overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-brand-600"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.4 }}
          />
        </div>
        <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
          <span>{elapsed}s</span>
          <span>{isCloud ? "Cloud-Modell" : "Lokales Modell"}</span>
        </div>
      </div>

      {/* Pipeline steps */}
      <div className="space-y-1">
        <AnimatePresence mode="popLayout">
          {steps.map((step, i) => (
            <motion.div
              key={`${i}-${step.label}`}
              initial={{ opacity: 0, x: -8, height: 0 }}
              animate={{ opacity: 1, x: 0, height: "auto" }}
              transition={{ duration: 0.2 }}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm",
                step.status === "active" && "bg-brand-50",
                step.status === "failed" && "bg-red-50/50",
              )}
            >
              <StepIcon status={step.status} />
              <span className="text-sm">{step.icon}</span>
              <span className={cn(
                "flex-1",
                step.status === "done" && "text-emerald-700",
                step.status === "failed" && "text-red-600",
                step.status === "active" && "text-brand-700 font-medium",
                step.status === "pending" && "text-muted-foreground",
              )}>
                {step.label}
              </span>
              {step.model && (
                <span className="text-[11px] text-muted-foreground font-mono">{step.model}</span>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
