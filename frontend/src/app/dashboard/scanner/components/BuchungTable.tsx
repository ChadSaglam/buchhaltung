"use client";

import { useState, useCallback } from "react";
import { motion } from "motion/react";
import { Download, Mail, Trash2, Send, Loader2, FileText, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import type { BuchungRow } from "../types";
import { formatCHF } from "../helpers";
import { ActionFeedback, type ActionFeedbackData } from "@/components/shared/ActionFeedback";

interface BuchungTableProps {
  rows: BuchungRow[];
  onRemove: (nr: number) => void;
  onClear: () => void;
}

const HEADERS = ["Nr", "Datum", "Beschreibung", "Soll", "Haben", "Betrag", "MwSt", "%", ""];

export function BuchungTable({ rows, onRemove, onClear }: BuchungTableProps) {
  const [exporting, setExporting] = useState<string | null>(null);
  const [emailTo, setEmailTo] = useState("");
  const [showEmail, setShowEmail] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [feedback, setFeedback] = useState<ActionFeedbackData | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const dismissFeedback = useCallback(() => setFeedback(null), []);

  if (rows.length === 0) return null;

  const totalAmount = rows.reduce((s, r) => s + r.betrag, 0);
  const now = () => new Date().toLocaleTimeString("de-CH", { hour: "2-digit", minute: "2-digit" });

  const handleExport = async (format: "banana" | "csv" | "excel") => {
    setExporting(format);
    try {
      const res = await api.post(
        `/api/export/${format}`,
        { rows },
        { responseType: "blob" }
      );
      const ext = format === "banana" ? "txt" : format === "excel" ? "xlsx" : "csv";
      const fileName = `scanner_buchungen.${ext}`;
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);

      setFeedback({
        type: "export",
        format,
        fileName,
        rowCount: rows.length,
        totalAmount: formatCHF(totalAmount),
        timestamp: now(),
      });
    } catch {
      toast.error("Export fehlgeschlagen");
    } finally {
      setExporting(null);
    }
  };

  const handleEmail = async () => {
    if (!emailTo) return;
    setSendingEmail(true);
    try {
      await api.post("/api/export/email/rows", {
        to_email: emailTo,
        rows,
      });
      setFeedback({
        type: "email",
        emailTo,
        rowCount: rows.length,
        totalAmount: formatCHF(totalAmount),
        timestamp: now(),
      });
      setShowEmail(false);
      setEmailTo("");
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || "E-Mail fehlgeschlagen";
      toast.error(msg);
    } finally {
      setSendingEmail(false);
    }
  };

  const handleClear = () => {
    if (!showClearConfirm) {
      setShowClearConfirm(true);
      return;
    }
    onClear();
    setShowClearConfirm(false);
    toast.success("Alle Buchungen gelöscht");
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-border bg-card overflow-hidden"
      >
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-brand-600" />
            <div>
              <p className="text-sm font-semibold text-foreground">{rows.length} Buchungen</p>
              <p className="text-xs text-muted-foreground">Total: {formatCHF(totalAmount)}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {(["banana", "csv", "excel"] as const).map((fmt) => (
              <button
                key={fmt}
                onClick={() => handleExport(fmt)}
                disabled={!!exporting}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-accent transition-colors disabled:opacity-50"
              >
                {exporting === fmt ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                {fmt.toUpperCase()}
              </button>
            ))}
            <button
              onClick={() => setShowEmail(!showEmail)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                showEmail
                  ? "border-brand-300 bg-brand-50 text-brand-700"
                  : "border-border text-muted-foreground hover:bg-accent"
              )}
            >
              <Mail className="h-3.5 w-3.5" /> E-Mail
            </button>

            {/* Clear with confirmation */}
            <button
              onClick={handleClear}
              onBlur={() => setTimeout(() => setShowClearConfirm(false), 200)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                showClearConfirm
                  ? "border-red-400 bg-red-50 text-red-700 animate-pulse"
                  : "border-red-200 text-red-600 hover:bg-red-50"
              )}
            >
              {showClearConfirm ? (
                <>
                  <AlertTriangle className="h-3.5 w-3.5" /> Wirklich löschen?
                </>
              ) : (
                <>
                  <Trash2 className="h-3.5 w-3.5" /> Alle löschen
                </>
              )}
            </button>
          </div>
        </div>

        {/* Email bar */}
        {showEmail && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="flex items-center gap-2 border-b border-border bg-accent/30 px-4 py-3"
          >
            <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
            <input
              type="email"
              value={emailTo}
              onChange={(e) => setEmailTo(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleEmail()}
              placeholder="empfaenger@firma.ch"
              className="flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
            />
            <button
              onClick={handleEmail}
              disabled={!emailTo || sendingEmail}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              {sendingEmail ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Send className="h-3.5 w-3.5" />
              )}
              {sendingEmail ? "Wird gesendet..." : "Senden"}
            </button>
          </motion.div>
        )}

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                {HEADERS.map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.nr} className="border-b border-border last:border-0 hover:bg-accent/30 transition-colors">
                  <td className="px-4 py-2.5 font-mono text-muted-foreground">{row.nr}</td>
                  <td className="px-4 py-2.5">{row.datum}</td>
                  <td className="px-4 py-2.5 max-w-[200px] truncate">{row.beschreibung}</td>
                  <td className="px-4 py-2.5 font-mono">{row.kt_soll}</td>
                  <td className="px-4 py-2.5 font-mono">{row.kt_haben}</td>
                  <td className="px-4 py-2.5 font-mono font-medium">{formatCHF(row.betrag)}</td>
                  <td className="px-4 py-2.5">{row.mwstcode}</td>
                  <td className="px-4 py-2.5">{row.mwstpct}</td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => onRemove(row.nr)}
                      className="rounded p-1 text-muted-foreground hover:text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            {/* Total row */}
            <tfoot>
              <tr className="bg-muted/30">
                <td colSpan={5} className="px-4 py-2.5 text-sm font-semibold text-foreground">Total</td>
                <td className="px-4 py-2.5 font-mono font-bold text-foreground">{formatCHF(totalAmount)}</td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          </table>
        </div>
      </motion.div>

      {/* Floating success feedback */}
      <ActionFeedback data={feedback} onDismiss={dismissFeedback} />
    </>
  );
}
