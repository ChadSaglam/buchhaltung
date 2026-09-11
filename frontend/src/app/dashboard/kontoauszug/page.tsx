"use client";
import { motion, AnimatePresence } from "motion/react";
import { FileText, Loader2, Save, RefreshCw, Download, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/ui/page_header";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/shared/ErrorState";
import { t } from "@/lib/i18n";
import { useKontoauszug } from "./hooks/useKontoauszug";
import { PdfDropZone } from "./components/PdfDropZone";
import { TransactionTable } from "./components/TransactionTable";
import type { ExportFormat } from "./types";

const EXPORTS: { format: ExportFormat; label: string }[] = [
  { format: "banana", label: "Banana TXT" },
  { format: "excel", label: "Excel" },
  { format: "csv", label: "CSV" },
];

const enter = { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0 }, transition: { duration: 0.25 } };

export default function KontoauszugPage() {
  const k = useKontoauszug();
  const lowConfidenceCount = k.rows.filter((r) => (r.confidence ?? 1) < 0.8).length;
  const busy = k.phase !== "idle";

  return (
    <div>
      <PageHeader icon={FileText} title={t("kontoauszug.title")} subtitle={t("kontoauszug.subtitle")} />

      <AnimatePresence mode="wait">
        {k.failure && !busy && (
          <motion.div key="error" {...enter}>
            <Card>
              <ErrorState error={k.failure.error} onRetry={k.retry} />
              <div className="flex justify-center pb-6">
                <Button variant="ghost" size="sm" onClick={k.reset}>Andere Datei wählen</Button>
              </div>
            </Card>
          </motion.div>
        )}

        {k.rows.length === 0 && !busy && !k.failure && (
          <motion.div key="dropzone" {...enter}>
            <PdfDropZone onFile={k.processFile} />
          </motion.div>
        )}

        {busy && (
          <motion.div key="processing" {...enter}>
            <Card>
              <CardContent className="flex flex-col items-center py-16">
                <Loader2 className="h-10 w-10 animate-spin text-brand-600 dark:text-brand-300 mb-4" aria-hidden="true" />
                <p className="text-muted-foreground" role="status" aria-live="polite">
                  {k.phase === "classifying" ? "Transaktionen werden klassifiziert..." : t("kontoauszug.processing")}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {k.rows.length > 0 && !busy && (
          <motion.div key="results" {...enter} className="space-y-4">
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-sm text-muted-foreground">{k.rows.length} Transaktionen</span>
              {lowConfidenceCount > 0 && <Badge tone="warning">{lowConfidenceCount} unsicher</Badge>}
              <Button variant="secondary" size="sm" icon={<Sparkles className="h-3.5 w-3.5" aria-hidden="true" />} onClick={k.acceptAll}>
                Alle AI-Vorschläge übernehmen
              </Button>
              <div className="flex-1" />
              {EXPORTS.map((e) => (
                <Button key={e.format} variant="outline" size="sm" icon={<Download className="h-3.5 w-3.5" aria-hidden="true" />} onClick={() => k.handleExport(e.format)}>
                  {e.label}
                </Button>
              ))}
            </div>

            <TransactionTable rows={k.rows} onUpdate={k.updateRow} onAccept={k.acceptSuggestion} />

            <div className="flex gap-3">
              <Button
                variant={k.saved ? "success" : "primary"}
                onClick={k.handleSave}
                disabled={k.saving || k.saved}
                loading={k.saving}
                icon={<Save className="h-4 w-4" aria-hidden="true" />}
              >
                {k.saved ? t("kontoauszug.saved") : t("kontoauszug.save")}
              </Button>
              <Button variant="ghost" icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />} onClick={k.reset}>
                Neue Datei
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
