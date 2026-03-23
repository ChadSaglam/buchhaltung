"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import toast from "react-hot-toast";
import api from "@/lib/api";
import { ScanLine } from "lucide-react";
import type { OllamaStatus, ExtractedInvoice, BuchungRow } from "./types";
import { calcMwst } from "./helpers";
import { StatusBar } from "./components/StatusBar";
import { DropZone } from "./components/DropZone";
import { ProcessingOverlay } from "./components/ProcessingOverlay";
import { InvoiceCard } from "./components/InvoiceCard";
import { BuchungTable } from "./components/BuchungTable";
import { ManualEntry } from "./components/ManualEntry";
import type { PipelineStep } from "./components/ProcessingOverlay";

export default function ScannerPage() {
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState("");
  const [processing, setProcessing] = useState(false);
  const [processingFile, setProcessingFile] = useState("");
  const [invoices, setInvoices] = useState<ExtractedInvoice[]>([]);
  const [addedIndices, setAddedIndices] = useState<Set<number>>(new Set());
  const [buchungen, setBuchungen] = useState<BuchungRow[]>([]);
  
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    api.get("/api/scanner/vision-status").then((res) => {
      setStatus(res.data);
      if (res.data.best_vision) setSelectedModel(res.data.best_vision);
      else if (res.data.models?.[0]) setSelectedModel(res.data.models[0].name);
    }).catch(() => setStatus({ ok: false })).finally(() => setStatusLoading(false));
  }, []);

  const processFiles = useCallback(async (files: File[]) => {
    for (const file of files) {
      setProcessing(true);
      setProcessingFile(file.name);
      setPipelineSteps([]);
      setElapsed(0);

      const timer = setInterval(() => setElapsed((s) => s + 1), 1000);

      try {
        const form = new FormData();
        form.append("file", file);
        if (selectedModel) form.append("model", selectedModel);

        const token = localStorage.getItem("token") || "";

        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/scanner/extract`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: form,
          }
        );

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || "Fehler beim Scannen");
        }

        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("text/event-stream")) {
          // SSE streaming
          const reader = response.body!.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";

            for (const block of lines) {
              const eventMatch = block.match(/^event: (.+)$/m);
              const dataMatch = block.match(/^data: (.+)$/m);
              if (!eventMatch || !dataMatch) continue;

              const eventType = eventMatch[1];
              const payload = JSON.parse(dataMatch[1]);

              if (eventType === "step") {
                setPipelineSteps((prev) => {
                  // Update existing active step or add new
                  const existing = prev.findIndex(
                    (s) => s.status === "active" && s.label === payload.label
                  );
                  if (existing >= 0) {
                    const updated = [...prev];
                    updated[existing] = payload;
                    return updated;
                  }
                  return [...prev, payload];
                });
              } else if (eventType === "result") {
                setInvoices((prev) => [...prev, payload.data]);
                toast.success(`${file.name} erkannt`);
              } else if (eventType === "error") {
                toast.error(payload.message);
              }
            }
          }
        } else {
          // Fallback: regular JSON response
          const json = await response.json();
          setInvoices((prev) => [...prev, json.data]);
          toast.success(`${file.name} erkannt`);
        }
      } catch (e: any) {
        toast.error(e.message || `Fehler bei ${file.name}`);
      } finally {
        clearInterval(timer);
      }
    }
    setProcessing(false);
    setProcessingFile("");
    setPipelineSteps([]);
  }, [selectedModel]);

  const addToBuchungen = (index: number) => {
    const inv = invoices[index];
    if (!inv || addedIndices.has(index)) return;
    const nr = buchungen.length + 1;
    const betrag = inv.total_amount;
    setBuchungen((prev) => [...prev, {
      nr,
      datum: inv.date || new Date().toISOString().slice(0, 10),
      beleg: "",
      rechnung: inv.invoice_number || "",
      beschreibung: `${inv.vendor} – ${inv.description}`.slice(0, 80),
      kt_soll: inv.kt_soll || "",
      kt_haben: inv.kt_haben || "",
      betrag,
      mwstcode: inv.mwst_code || "",
      artbetrag: inv.mwst_code ? "1" : "",
      mwstpct: inv.mwst_pct || "",
      mwstchf: calcMwst(betrag, inv.mwst_pct || ""),
      ks3: "",
    }]);
    setAddedIndices((prev) => new Set(prev).add(index));
  };

  const updateInvoice = (index: number, updated: ExtractedInvoice) => {
    setInvoices((prev) => prev.map((inv, i) => i === index ? updated : inv));
  };

  const isCloud = selectedModel.endsWith(":cloud") || selectedModel.endsWith("-cloud");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <ScanLine className="h-6 w-6 text-brand-600" />
          <h1 className="text-2xl font-bold text-foreground">Rechnung Scanner</h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Rechnung hochladen → AI erkennt Details → automatische Kontierung
        </p>
      </div>

      {/* Status */}
      <StatusBar
        status={status}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        loading={statusLoading}
      />

      {/* Upload / Processing */}
      <AnimatePresence mode="wait">
        {processing ? (
          <ProcessingOverlay
            key="processing"
            steps={pipelineSteps}
            fileName={processingFile}
            elapsed={elapsed}
            isCloud={selectedModel.endsWith(":cloud") || selectedModel.endsWith("-cloud")}
          />
        ) : invoices.length === 0 ? (
          <motion.div key="dropzone" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <DropZone onFilesAccepted={processFiles} disabled={processing} />
          </motion.div>
        ) : (
          <motion.div key="compact-drop" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <DropZone onFilesAccepted={processFiles} disabled={processing} compact />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Extracted invoices */}
      {invoices.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Erkannte Rechnungen</h2>
          {invoices.map((inv, i) => (
            <InvoiceCard
              key={i}
              invoice={inv}
              index={i}
              onUpdate={(updated) => updateInvoice(i, updated)}
              onAddToBookings={() => addToBuchungen(i)}
              added={addedIndices.has(i)}
            />
          ))}
        </div>
      )}

      {/* Manual entry */}
      <ManualEntry onAddRow={(row) => setBuchungen((prev) => [...prev, row])} nextNr={buchungen.length + 1} />

      {/* Booking table */}
      <BuchungTable
        rows={buchungen}
        onRemove={(nr) => setBuchungen((prev) => prev.filter((r) => r.nr !== nr))}
        onClear={() => { setBuchungen([]); setAddedIndices(new Set()); }}
      />
    </div>
  );
}
