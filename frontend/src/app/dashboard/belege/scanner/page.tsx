"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ScanLine } from "lucide-react";
import type { BuchungRow } from "./types";
import { calcMwst } from "./helpers";
import { useScanner } from "./hooks/useScanner";
import { StatusBar } from "./components/StatusBar";
import { DropZone } from "./components/DropZone";
import { ProcessingOverlay } from "./components/ProcessingOverlay";
import { InvoiceCard } from "./components/InvoiceCard";
import { BuchungTable } from "./components/BuchungTable";
import { ManualEntry } from "./components/ManualEntry";
import { PageHeader } from "@/components/ui/page_header";
import { ErrorState } from "@/components/shared/ErrorState";
import { t } from "@/lib/i18n";

export default function ScannerPage() {
  const s = useScanner();
  const [addedIndices, setAddedIndices] = useState<Set<number>>(new Set());
  const [buchungen, setBuchungen] = useState<BuchungRow[]>([]);

  const addToBuchungen = (index: number) => {
    const inv = s.invoices[index];
    if (!inv || addedIndices.has(index)) return;
    const betrag = inv.total_amount;
    setBuchungen((prev) => [
      ...prev,
      {
        nr: prev.length + 1,
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
      },
    ]);
    setAddedIndices((prev) => new Set(prev).add(index));
  };

  return (
    <div className="space-y-6">
      <PageHeader icon={ScanLine} title={t("scanner.title")} subtitle={t("scanner.subtitle")} />

      <StatusBar status={s.status} selectedModel={s.selectedModel} onModelChange={s.setSelectedModel} loading={s.statusLoading} />

      {s.failure && !s.processing && (
        <ErrorState
          error={s.failure.error}
          onRetry={s.retry}
          title={`${s.failure.file.name}: ${t("common.error")}`}
          variant="inline"
        />
      )}

      <AnimatePresence mode="wait">
        {s.processing ? (
          <ProcessingOverlay
            key="processing"
            steps={s.pipelineSteps}
            fileName={s.processingFile}
            elapsed={s.elapsed}
            isCloud={s.isCloud}
          />
        ) : (
          <motion.div key={s.invoices.length === 0 ? "dropzone" : "compact-drop"} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <DropZone onFilesAccepted={s.processFiles} disabled={s.processing} compact={s.invoices.length > 0} />
          </motion.div>
        )}
      </AnimatePresence>

      {s.invoices.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-foreground">Erkannte Rechnungen</h2>
          {s.invoices.map((inv, i) => (
            <InvoiceCard
              key={i}
              invoice={inv}
              index={i}
              onUpdate={(updated) => s.updateInvoice(i, updated)}
              onAddToBookings={() => addToBuchungen(i)}
              added={addedIndices.has(i)}
            />
          ))}
        </div>
      )}

      <ManualEntry onAddRow={(row) => setBuchungen((prev) => [...prev, row])} nextNr={buchungen.length + 1} />

      <BuchungTable
        rows={buchungen}
        onRemove={(nr) => setBuchungen((prev) => prev.filter((r) => r.nr !== nr))}
        onClear={() => {
          setBuchungen([]);
          setAddedIndices(new Set());
        }}
      />
    </div>
  );
}
