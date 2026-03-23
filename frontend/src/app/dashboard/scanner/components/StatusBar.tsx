"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { CheckCircle, AlertTriangle, Cpu, ChevronDown, Eye, Zap, Monitor } from "lucide-react";
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
}

function ModelBadge({ isVision, isCloud }: { isVision: boolean; isCloud: boolean }) {
  return (
    <span className="inline-flex items-center gap-1">
      {isVision && (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700">
          <Eye className="h-2.5 w-2.5" /> Vision
        </span>
      )}
      {isCloud && (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
          <Zap className="h-2.5 w-2.5" /> Cloud
        </span>
      )}
      {!isCloud && (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
          <Monitor className="h-2.5 w-2.5" /> Lokal
        </span>
      )}
    </span>
  );
}

export function StatusBar({ status, selectedModel, onModelChange, loading }: StatusBarProps) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 animate-pulse">
        <div className="h-5 w-5 rounded-full bg-muted" />
        <div className="h-4 w-48 rounded bg-muted" />
      </div>
    );
  }

  const visionModels = status?.vision_models ?? [];
  const allModels: ModelOption[] = (status?.models ?? []).map((m) => ({
    name: m.name,
    isVision: visionModels.includes(m.name),
    isCloud: m.name.endsWith(":cloud") || m.name.endsWith("-cloud"),
  }));
  const isOk = status?.ok ?? false;
  const selected = allModels.find((m) => m.name === selectedModel);

  // Sort: vision+cloud first, then vision, then cloud, then local
  const sortedModels = [...allModels].sort((a, b) => {
    const score = (m: ModelOption) => (m.isVision ? 2 : 0) + (m.isCloud ? 1 : 0);
    return score(b) - score(a);
  });

  return (
    <div className={cn(
      "flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4",
      isOk ? "border-emerald-200 bg-emerald-50/50" : "border-amber-200 bg-amber-50/50"
    )}>
      <div className="flex items-center gap-3">
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
      </div>

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
            <span className="font-medium text-foreground max-w-[180px] truncate">
              {selectedModel || "Modell wählen"}
            </span>
            {selected && <ModelBadge isVision={selected.isVision} isCloud={selected.isCloud} />}
            <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
          </button>

          <AnimatePresence>
            {open && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full z-50 mt-1 w-80 rounded-xl border border-border bg-card shadow-xl shadow-black/10 overflow-hidden"
              >
                <div className="px-3 py-2 border-b border-border">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Modell auswählen
                  </p>
                </div>
                <div className="max-h-64 overflow-y-auto py-1">
                  {sortedModels.map((model) => (
                    <button
                      key={model.name}
                      onClick={() => { onModelChange(model.name); setOpen(false); }}
                      className={cn(
                        "flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left transition-colors",
                        model.name === selectedModel
                          ? "bg-brand-50 text-brand-700"
                          : "hover:bg-accent text-foreground"
                      )}
                    >
                      <div className="min-w-0">
                        <p className={cn(
                          "text-sm font-medium truncate",
                          model.name === selectedModel && "text-brand-700"
                        )}>
                          {model.name}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {model.isCloud ? "Cloud-Modell — schneller" : "Lokales Modell — privat"}
                        </p>
                      </div>
                      <ModelBadge isVision={model.isVision} isCloud={model.isCloud} />
                    </button>
                  ))}
                </div>
                {allModels.length === 0 && (
                  <p className="px-3 py-4 text-sm text-muted-foreground text-center">
                    Keine Modelle verfügbar
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
