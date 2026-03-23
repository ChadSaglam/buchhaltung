"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { CheckCircle2, Mail, Download, X, ExternalLink, Undo2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type FeedbackType = "export" | "email";

export interface ActionFeedbackData {
  type: FeedbackType;
  format?: string;
  fileName?: string;
  emailTo?: string;
  rowCount: number;
  totalAmount: string;
  timestamp: string;
}

interface ActionFeedbackProps {
  data: ActionFeedbackData | null;
  onDismiss: () => void;
  onUndo?: () => void;
}

export function ActionFeedback({ data, onDismiss, onUndo }: ActionFeedbackProps) {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!data) return;
    setProgress(100);
    const duration = 8000;
    const interval = 50;
    const step = (interval / duration) * 100;
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev <= 0) {
          clearInterval(timer);
          onDismiss();
          return 0;
        }
        return prev - step;
      });
    }, interval);
    return () => clearInterval(timer);
  }, [data, onDismiss]);

  const isEmail = data?.type === "email";
  const Icon = isEmail ? Mail : Download;
  const title = isEmail
    ? `E-Mail gesendet`
    : `${data?.format?.toUpperCase()} exportiert`;
  const subtitle = isEmail
    ? `An ${data?.emailTo}`
    : data?.fileName;

  return (
    <AnimatePresence>
      {data && (
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
          className="fixed bottom-6 right-6 z-50 w-[380px] overflow-hidden rounded-xl border border-emerald-200 bg-white shadow-2xl shadow-emerald-500/10"
        >
          {/* Auto-dismiss progress */}
          <div className="h-1 bg-emerald-100">
            <motion.div
              className="h-full bg-emerald-500"
              initial={{ width: "100%" }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.05 }}
            />
          </div>

          <div className="p-4">
            <div className="flex items-start gap-3">
              {/* Success icon */}
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", delay: 0.1 }}
                >
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                </motion.div>
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-foreground">{title}</p>
                  <button
                    onClick={onDismiss}
                    className="rounded-md p-1 text-muted-foreground hover:bg-accent transition-colors"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground truncate">{subtitle}</p>

                {/* Stats */}
                <div className="mt-3 flex items-center gap-3">
                  <div className="flex items-center gap-1.5 rounded-md bg-accent px-2.5 py-1">
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs font-medium text-foreground">
                      {data.rowCount} Buchung{data.rowCount !== 1 && "en"}
                    </span>
                  </div>
                  <div className="rounded-md bg-accent px-2.5 py-1">
                    <span className="text-xs font-medium text-foreground">{data.totalAmount}</span>
                  </div>
                  <span className="text-[11px] text-muted-foreground">{data.timestamp}</span>
                </div>
              </div>
            </div>

            {/* Actions */}
            {isEmail && (
              <div className="mt-3 flex items-center gap-2 pl-[52px]">
                <button
                  onClick={onDismiss}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
                >
                  <ExternalLink className="h-3 w-3" /> OK
                </button>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
