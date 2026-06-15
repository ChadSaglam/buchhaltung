"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  CheckCircle,
  AlertTriangle,
  Cpu,
  ChevronDown,
  Eye,
  Zap,
  Monitor,
  Info,
  Wrench,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { OllamaStatus } from "../types";

interface StatusBarProps {
  status: OllamaStatus | null;
  selectedModel: string;
  onModelChange: (model: string) => void;
  loading: boolean;
}

interface ModelOption {
  name: string;
  isVision: boolean;
  isCloud: boolean;
  provider?: string;
  available?: boolean;
  working?: boolean;
  statusLabel?: string;
}

function ModelBadge({
  isVision,
  isCloud,
  available,
  statusLabel,
}: {
  isVision: boolean;
  isCloud: boolean;
  available?: boolean;
  statusLabel?: string;
}) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {isVision ? (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700">
          <Eye className="h-2.5 w-2.5" /> Vision
        </span>
      ) : (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-orange-100 px-1.5 py-0.5 text-[10px] font-medium text-orange-700">
          <Wrench className="h-2.5 w-2.5" /> OCR
        </span>
      )}

      {isCloud ? (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
          <Zap className="h-2.5 w-2.5" /> Cloud
        </span>
      ) : (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
          <Monitor className="h-2.5 w-2.5" /> Lokal
        </span>
      )}

      {available ? (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
          <CheckCircle className="h-2.5 w-2.5" /> {statusLabel || "bereit"}
        </span>
      ) : (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700">
          <XCircle className="h-2.5 w-2.5" /> {statusLabel || "nicht bereit"}
        </span>
      )}
    </span>
  );
}

export function StatusBar({ status, selectedModel, onModelChange, loading }: StatusBarProps) {
  const [open, setOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  if (loading) {
    return (
      <div className="flex animate-pulse items-center gap-3 rounded-xl border border-border bg-card p-4">
        <div className="h-5 w-5 rounded-full bg-muted" />
        <div className="h-4 w-48 rounded bg-muted" />
      </div>
    );
  }

  const visionModels = status?.vision_models ?? [];
  const allModels: ModelOption[] = (status?.models ?? []).map((m) => ({
    name: m.name,
    isVision: visionModels.includes(m.name) || m.provider === "vision",
    isCloud: m.kind === "cloud" || m.name.endsWith(":cloud") || m.name.endsWith("-cloud"),
    provider: m.provider,
    available: m.available ?? true,
    working: m.working ?? true,
    statusLabel: m.status_label,
  }));
  const isOk = status?.ok ?? false;
  const selected = allModels.find((m) => m.name === selectedModel);

  const sortedModels = [...allModels].sort((a, b) => {
    const score = (m: ModelOption) =>
      (m.available ? 100 : 0) +
      (m.isVision ? 20 : 0) +
      (m.isCloud ? 10 : 0);
    return score(b) - score(a);
  });

  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        isOk ? "border-emerald-200 bg-emerald-50/50" : "border-amber-200 bg-amber-50/50"
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => setDetailsOpen((v) => !v)}
          className="flex items-center gap-3 text-left"
        >
          {isOk ? (
            <CheckCircle className="h-5 w-5 text-emerald-600" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-amber-600" />
          )}
          <div>
            <p className={cn("text-sm font-medium", isOk ? "text-emerald-800" : "text-amber-800")}>
              {isOk ? "Vision AI bereit" : "Vision nicht verfügbar — ML-Klassifizierung aktiv"}
            </p>
            {isOk && (
              <p className="text-xs text-emerald-600">
                {visionModels.length} Vision · {allModels.length - visionModels.length} Text · {allModels.length} Total
              </p>
            )}
          </div>
          <Info className="h-4 w-4 text-muted-foreground" />
        </button>

        {isOk && allModels.length > 0 && (
          <div ref={dropdownRef} className="relative">
            <button
              onClick={() => setOpen(!open)}
              className={cn(
                "flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm transition-all",
                open ? "border-brand-300 ring-2 ring-brand-100" : "border-input hover:border-brand-200"
              )}
            >
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <span className="max-w-[180px] truncate font-medium text-foreground">
                {selectedModel || "Modell wählen"}
              </span>
              {selected && (
                <ModelBadge
                  isVision={selected.isVision}
                  isCloud={selected.isCloud}
                  available={selected.available}
                  statusLabel={selected.statusLabel}
                />
              )}
              <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
            </button>

            <AnimatePresence>
              {open && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.97 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full z-50 mt-1 w-[28rem] overflow-hidden rounded-xl border border-border bg-card shadow-xl shadow-black/10"
                >
                  <div className="border-b border-border px-3 py-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Modell auswählen
                    </p>
                  </div>
                  <div className="max-h-80 overflow-y-auto py-1">
                    {sortedModels.map((model) => (
                      <button
                        key={model.name}
                        onClick={() => {
                          if (model.available) {
                            onModelChange(model.name);
                          }
                          setOpen(false);
                        }}
                        disabled={!model.available}
                        className={cn(
                          "flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left transition-colors",
                          model.name === selectedModel
                            ? "bg-brand-50 text-brand-700"
                            : "text-foreground hover:bg-accent",
                          !model.available && "cursor-not-allowed opacity-60"
                        )}
                      >
                        <div className="min-w-0">
                          <p
                            className={cn(
                              "truncate text-sm font-medium",
                              model.name === selectedModel && "text-brand-700"
                            )}
                          >
                            {model.name}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {model.provider === "ocr"
                              ? model.available
                                ? "Eigene OCR verfügbar"
                                : "Eigene OCR nicht implementiert"
                              : model.isCloud
                                ? "Cloud-Modell"
                                : "Lokales Modell"}
                          </p>
                        </div>
                        <ModelBadge
                          isVision={model.isVision}
                          isCloud={model.isCloud}
                          available={model.available}
                          statusLabel={model.statusLabel}
                        />
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      <AnimatePresence>
        {detailsOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: "auto", marginTop: 16 }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            className="overflow-hidden border-t border-border/60 pt-4"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Pipeline
                </p>
                <div className="space-y-2">
                  {(status?.pipeline ?? []).map((step) => (
                    <div key={`${step.step}-${step.type}`} className="rounded-lg bg-background/80 px-3 py-2 text-sm">
                      <p className="font-medium text-foreground">
                        {step.step}. {step.type}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {step.name
                          ? step.name
                          : step.models?.length
                            ? step.models.join(", ")
                            : "—"}
                      </p>
                      {step.type === "ocr" && (
                        <p className={cn(
                          "mt-1 text-[11px]",
                          step.available ? "text-emerald-700" : "text-red-600"
                        )}>
                          {step.status_label || (step.available ? "bereit" : "nicht implementiert")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Verfügbare Modelle
                </p>
                <div className="space-y-2">
                  {sortedModels.map((model) => (
                    <div
                      key={`details-${model.name}`}
                      className="flex items-center justify-between rounded-lg bg-background/80 px-3 py-2 text-sm"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-foreground">{model.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {model.provider === "ocr"
                            ? model.available
                              ? "Eigene OCR verfügbar"
                              : "Eigene OCR nicht implementiert"
                            : model.provider || "model"}
                        </p>
                      </div>
                      <ModelBadge
                        isVision={model.isVision}
                        isCloud={model.isCloud}
                        available={model.available}
                        statusLabel={model.statusLabel}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}