"use client";

import { useState } from "react";
import { motion } from "motion/react";
import {
  CheckCircle, Edit3, Save, RotateCcw, ChevronDown, ChevronUp,
  FileText, Calculator
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ExtractedInvoice, MWST_CODE_OPTIONS, MWST_PCT_OPTIONS } from "../types";
import { sourceIcon, formatCHF, calcMwst } from "../helpers";

interface InvoiceCardProps {
  invoice: ExtractedInvoice;
  index: number;
  onUpdate: (invoice: ExtractedInvoice) => void;
  onAddToBookings: () => void;
  added: boolean;
}

function Field({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
      {children}
    </div>
  );
}

export function InvoiceCard({ invoice, index, onUpdate, onAddToBookings, added }: InvoiceCardProps) {
  const [editing, setEditing] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [draft, setDraft] = useState(invoice);

  const confidence = invoice.classification_confidence ?? 0;
  const classSource = invoice.classification_source ?? "–";

  const handleSaveEdit = () => {
    onUpdate(draft);
    setEditing(false);
  };

  const handleCancelEdit = () => {
    setDraft(invoice);
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
        "rounded-xl border bg-card overflow-hidden transition-shadow hover:shadow-lg hover:shadow-black/5",
        added ? "border-emerald-200" : "border-border"
      )}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between gap-4 p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold",
            added ? "bg-emerald-100 text-emerald-700" : "bg-brand-50 text-brand-700"
          )}>
            {added ? <CheckCircle className="h-4 w-4" /> : index + 1}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">{invoice.vendor || "Unbekannt"}</p>
            <p className="text-xs text-muted-foreground">
              {invoice.date} · {invoice.invoice_number} · {formatCHF(invoice.total_amount)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn(
            "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium",
            confidence >= 0.8 ? "bg-emerald-100 text-emerald-700"
              : confidence >= 0.5 ? "bg-amber-100 text-amber-700"
              : "bg-red-100 text-red-700"
          )}>
            {sourceIcon(classSource)} {(confidence * 100).toFixed(0)}%
          </span>
          {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </div>
      </div>

      {/* Body */}
      {expanded && (
        <div className="border-t border-border p-4 space-y-4">
          {/* Invoice details */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Field label="Lieferant">
              {editing ? (
                <input className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm" value={draft.vendor} onChange={(e) => updateDraft("vendor", e.target.value)} />
              ) : (
                <p className="text-sm font-medium text-foreground">{invoice.vendor}</p>
              )}
            </Field>
            <Field label="Datum">
              {editing ? (
                <input type="date" className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm" value={draft.date} onChange={(e) => updateDraft("date", e.target.value)} />
              ) : (
                <p className="text-sm text-foreground">{invoice.date}</p>
              )}
            </Field>
            <Field label="Betrag">
              {editing ? (
                <input type="number" step="0.01" className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm" value={draft.total_amount} onChange={(e) => updateDraft("total_amount", parseFloat(e.target.value))} />
              ) : (
                <p className="text-sm font-semibold text-foreground">{formatCHF(invoice.total_amount)}</p>
              )}
            </Field>
            <Field label="Rechnung Nr.">
              {editing ? (
                <input className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm" value={draft.invoice_number} onChange={(e) => updateDraft("invoice_number", e.target.value)} />
              ) : (
                <p className="text-sm text-foreground">{invoice.invoice_number || "–"}</p>
              )}
            </Field>
          </div>

          {/* Beschreibung */}
          <Field label="Beschreibung">
            {editing ? (
              <input className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm" value={draft.description} onChange={(e) => updateDraft("description", e.target.value)} />
            ) : (
              <p className="text-sm text-foreground">{invoice.description || "–"}</p>
            )}
          </Field>

          {/* Kontierung */}
          <div className="rounded-lg bg-accent/50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              <Calculator className="inline h-3.5 w-3.5 mr-1 -mt-0.5" /> Kontierung
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <Field label="Kto Soll">
                {editing ? (
                  <input className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm font-mono" value={draft.kt_soll ?? ""} onChange={(e) => updateDraft("kt_soll", e.target.value)} />
                ) : (
                  <p className="text-sm font-mono font-medium text-foreground">{invoice.kt_soll || "–"}</p>
                )}
              </Field>
              <Field label="Kto Haben">
                {editing ? (
                  <input className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm font-mono" value={draft.kt_haben ?? ""} onChange={(e) => updateDraft("kt_haben", e.target.value)} />
                ) : (
                  <p className="text-sm font-mono font-medium text-foreground">{invoice.kt_haben || "–"}</p>
                )}
              </Field>
              <Field label="MwSt-Code">
                {editing ? (
                  <input className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm" value={draft.mwst_code ?? ""} onChange={(e) => updateDraft("mwst_code", e.target.value)} />
                ) : (
                  <p className="text-sm text-foreground">{invoice.mwst_code || "–"}</p>
                )}
              </Field>
              <Field label="MwSt-%">
                {editing ? (
                  <input className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm" value={draft.mwst_pct ?? ""} onChange={(e) => updateDraft("mwst_pct", e.target.value)} />
                ) : (
                  <p className="text-sm text-foreground">{invoice.mwst_pct ? `${invoice.mwst_pct}%` : "–"}</p>
                )}
              </Field>
            </div>
          </div>

          {/* Line items */}
          {invoice.line_items?.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Positionen</p>
              <div className="space-y-1">
                {invoice.line_items.map((li, i) => (
                  <div key={i} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-1.5 text-sm">
                    <span className="text-foreground">{li.item}</span>
                    <span className="font-mono text-muted-foreground">{formatCHF(li.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2">
            {editing ? (
              <>
                <button onClick={handleSaveEdit} className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors">
                  <Save className="h-3.5 w-3.5" /> Übernehmen
                </button>
                <button onClick={handleCancelEdit} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent transition-colors">
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
                      ? "bg-emerald-100 text-emerald-700 cursor-default"
                      : "bg-brand-600 text-white hover:bg-brand-700"
                  )}
                >
                  {added ? <CheckCircle className="h-3.5 w-3.5" /> : <FileText className="h-3.5 w-3.5" />}
                  {added ? "Hinzugefügt" : "Zur Buchung"}
                </button>
                <button onClick={() => setEditing(true)} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent transition-colors">
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
