"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  CheckCircle,
  Edit3,
  Save,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  FileText,
  Calculator,
  Cpu,
  Eye,
  Brain,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { MWST_CODE_OPTIONS, MWST_PCT_OPTIONS, type ExtractedInvoice } from "../types";
import { sourceIcon, formatCHF } from "../helpers";

interface InvoiceCardProps {
  invoice?: ExtractedInvoice;
  index: number;
  onUpdate: (invoice: ExtractedInvoice) => void;
  onAddToBookings: () => void;
  added: boolean;
}

function Field({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

export function InvoiceCard({ invoice, index, onUpdate, onAddToBookings, added }: InvoiceCardProps) {
  const [editing, setEditing] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [showTech, setShowTech] = useState(false);

  const safeInvoice: ExtractedInvoice = invoice ?? {
    vendor: "",
    date: "",
    invoice_number: "",
    description: "",
    total_amount: 0,
    vat_rate: 0,
    line_items: [],
    kt_soll: "",
    kt_haben: "",
    mwst_code: "",
    mwst_pct: "",
    mwst_amount: 0,
    classification_confidence: 0,
    classification_source: "",
    classification_input: "",
    vision_model: "",
    ocr_provider: "",
    ocr_worked: false,
    custom_ocr_available: false,
    scanner_steps: [],
    scanner_attempts: [],
    scanner_providers: [],
  };

  const [draft, setDraft] = useState<ExtractedInvoice>(safeInvoice);

  useEffect(() => {
    setDraft(safeInvoice);
  }, [invoice]);

  const confidence = safeInvoice.classification_confidence ?? 0;
  const classSource = safeInvoice.classification_source ?? "–";

  const handleSaveEdit = () => {
    onUpdate(draft);
    setEditing(false);
  };

  const handleCancelEdit = () => {
    setDraft(safeInvoice);
    setEditing(false);
  };

  const updateDraft = (key: keyof ExtractedInvoice, value: string | number) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
      className={cn(
        "overflow-hidden rounded-xl border bg-card transition-shadow hover:shadow-lg hover:shadow-black/5",
        added ? "border-emerald-200" : "border-border"
      )}
    >

      <div className="rounded-lg border border-border bg-background/60">
            <button
              type="button"
              onClick={() => setShowTech((v) => !v)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <Cpu className="h-3.5 w-3.5" /> Scanner Details
              </span>
              {showTech ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </button>

            <AnimatePresence>
              {showTech && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden border-t border-border px-4 py-3"
                >
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="OCR">
                      <p className="text-sm text-foreground">{safeInvoice.ocr_provider || "–"}</p>
                    </Field>
                    <Field label="Vision-Modell">
                      <p className="text-sm text-foreground">{safeInvoice.vision_model || "–"}</p>
                    </Field>
                    <Field label="Eigene OCR Status">
                      <div className="flex items-center gap-2 text-sm">
                        {safeInvoice.ocr_worked ? (
                          <>
                            <CheckCircle className="h-4 w-4 text-emerald-600" />
                            <span className="text-emerald-700">Erfolgreich verwendet</span>
                          </>
                        ) : safeInvoice.custom_ocr_available ? (
                          <>
                            <XCircle className="h-4 w-4 text-amber-600" />
                            <span className="text-amber-700">Verfügbar, aber in diesem Lauf nicht erfolgreich</span>
                          </>
                        ) : (
                          <>
                            <XCircle className="h-4 w-4 text-red-600" />
                            <span className="text-red-700">Nicht implementiert</span>
                          </>
                        )}
                      </div>
                    </Field>
                    <Field label="Kontierung Quelle">
                      <p className="text-sm text-foreground">{safeInvoice.classification_source || "–"}</p>
                    </Field>
                    <Field label="Kontierung Input" className="sm:col-span-2">
                      <p className="break-words text-sm text-foreground">{safeInvoice.classification_input || "–"}</p>
                    </Field>
                  </div>

                  {safeInvoice.scanner_steps && safeInvoice.scanner_steps.length > 0 && (
                    <div className="mt-4">
                      <p className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        <Brain className="h-3.5 w-3.5" /> Ablauf
                      </p>
                      <div className="space-y-2">
                        {safeInvoice.scanner_steps.map((step, stepIndex) => (
                          <div
                            key={`${stepIndex}-${step.label}`}
                            className="rounded-md bg-muted/40 px-3 py-2 text-sm"
                          >
                            <div className="flex items-center gap-2">
                              <span>{step.icon}</span>
                              <span className="font-medium text-foreground">{step.label}</span>
                            </div>
                            <div className="mt-1 text-[11px] text-muted-foreground">
                              {[step.provider, step.model, step.source, typeof step.confidence === "number" ? `${Math.round(step.confidence * 100)}%` : null]
                                .filter(Boolean)
                                .join(" · ")}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {safeInvoice.scanner_attempts && safeInvoice.scanner_attempts.length > 0 && (
                    <div className="mt-4">
                      <p className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        <Eye className="h-3.5 w-3.5" /> Modellversuche
                      </p>
                      <div className="space-y-2">
                        {safeInvoice.scanner_attempts.map((attempt, attemptIndex) => (
                          <div
                            key={`${attempt.name}-${attemptIndex}`}
                            className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-2 text-sm"
                          >
                            <span className="text-foreground">
                              {attempt.provider} · {attempt.name} · {attempt.kind}
                            </span>
                            <span
                              className={cn(
                                "text-xs",
                                attempt.status === "done" && "text-emerald-700",
                                attempt.status === "failed" && "text-red-600",
                                attempt.status === "active" && "text-brand-700",
                                attempt.status === "pending" && "text-muted-foreground"
                              )}
                            >
                              {attempt.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          
      <div
        className="flex cursor-pointer items-center justify-between gap-4 p-4"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex min-w-0 items-center gap-3">
          <div
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold",
              added ? "bg-emerald-100 text-emerald-700" : "bg-brand-50 text-brand-700"
            )}
          >
            {added ? <CheckCircle className="h-4 w-4" /> : index + 1}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{safeInvoice.vendor || "Unbekannt"}</p>
            <p className="text-xs text-muted-foreground">
              {safeInvoice.date} · {safeInvoice.invoice_number} · {formatCHF(safeInvoice.total_amount)}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium",
              confidence >= 0.8
                ? "bg-emerald-100 text-emerald-700"
                : confidence >= 0.5
                  ? "bg-amber-100 text-amber-700"
                  : "bg-red-100 text-red-700"
            )}
          >
            {sourceIcon(classSource)} {(confidence * 100).toFixed(0)}%
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="space-y-4 border-t border-border p-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Field label="Lieferant">
              {editing ? (
                <input
                  className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                  value={draft.vendor}
                  onChange={(e) => updateDraft("vendor", e.target.value)}
                />
              ) : (
                <p className="text-sm font-medium text-foreground">{safeInvoice.vendor}</p>
              )}
            </Field>

            <Field label="Datum">
              {editing ? (
                <input
                  type="date"
                  className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                  value={draft.date}
                  onChange={(e) => updateDraft("date", e.target.value)}
                />
              ) : (
                <p className="text-sm text-foreground">{safeInvoice.date}</p>
              )}
            </Field>

            <Field label="Betrag">
              {editing ? (
                <input
                  type="number"
                  step="0.01"
                  className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                  value={draft.total_amount}
                  onChange={(e) => updateDraft("total_amount", parseFloat(e.target.value || "0"))}
                />
              ) : (
                <p className="text-sm font-semibold text-foreground">{formatCHF(safeInvoice.total_amount)}</p>
              )}
            </Field>

            <Field label="Rechnung Nr.">
              {editing ? (
                <input
                  className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                  value={draft.invoice_number}
                  onChange={(e) => updateDraft("invoice_number", e.target.value)}
                />
              ) : (
                <p className="text-sm text-foreground">{safeInvoice.invoice_number || "–"}</p>
              )}
            </Field>
          </div>

          <Field label="Beschreibung">
            {editing ? (
              <input
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                value={draft.description}
                onChange={(e) => updateDraft("description", e.target.value)}
              />
            ) : (
              <p className="text-sm text-foreground">{safeInvoice.description || "–"}</p>
            )}
          </Field>

          <div className="rounded-lg bg-accent/50 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Calculator className="mr-1 inline h-3.5 w-3.5 -mt-0.5" /> Kontierung
            </p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Field label="Kto Soll">
                {editing ? (
                  <input
                    className="w-full rounded-md border border-input bg-background px-2 py-1 font-mono text-sm"
                    value={draft.kt_soll ?? ""}
                    onChange={(e) => updateDraft("kt_soll", e.target.value)}
                  />
                ) : (
                  <p className="font-mono text-sm font-medium text-foreground">{safeInvoice.kt_soll || "–"}</p>
                )}
              </Field>

              <Field label="Kto Haben">
                {editing ? (
                  <input
                    className="w-full rounded-md border border-input bg-background px-2 py-1 font-mono text-sm"
                    value={draft.kt_haben ?? ""}
                    onChange={(e) => updateDraft("kt_haben", e.target.value)}
                  />
                ) : (
                  <p className="font-mono text-sm font-medium text-foreground">{safeInvoice.kt_haben || "–"}</p>
                )}
              </Field>

              <Field label="MwSt-Code">
                {editing ? (
                  <select
                    className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                    value={draft.mwst_code ?? ""}
                    onChange={(e) => updateDraft("mwst_code", e.target.value)}
                  >
                    {MWST_CODE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option || "–"}
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="text-sm text-foreground">{safeInvoice.mwst_code || "–"}</p>
                )}
              </Field>

              <Field label="MwSt-%">
                {editing ? (
                  <select
                    className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                    value={draft.mwst_pct ?? ""}
                    onChange={(e) => updateDraft("mwst_pct", e.target.value)}
                  >
                    {MWST_PCT_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option || "–"}
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="text-sm text-foreground">{safeInvoice.mwst_pct ? `${safeInvoice.mwst_pct}%` : "–"}</p>
                )}
              </Field>
            </div>
          </div>

          {safeInvoice.line_items?.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Positionen</p>
              <div className="space-y-1">
                {safeInvoice.line_items.map((li, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-1.5 text-sm"
                  >
                    <span className="text-foreground">{li.item}</span>
                    <span className="font-mono text-muted-foreground">{formatCHF(li.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 pt-2">
            {editing ? (
              <>
                <button
                  onClick={handleSaveEdit}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700"
                >
                  <Save className="h-3.5 w-3.5" /> Übernehmen
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Abbrechen
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={onAddToBookings}
                  disabled={added}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    added
                      ? "cursor-default bg-emerald-100 text-emerald-700"
                      : "bg-brand-600 text-white hover:bg-brand-700"
                  )}
                >
                  {added ? <CheckCircle className="h-3.5 w-3.5" /> : <FileText className="h-3.5 w-3.5" />}
                  {added ? "Hinzugefügt" : "Zur Buchung"}
                </button>
                <button
                  onClick={() => setEditing(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
                >
                  <Edit3 className="h-3.5 w-3.5" /> Bearbeiten
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}