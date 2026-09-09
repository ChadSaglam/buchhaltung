"use client";

import { Upload, CheckCircle, Loader2, FileSpreadsheet, Trash2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import { useBananaImport } from "../hooks/useBananaImport";

export function BananaImportCard({ fetchInfo }: { fetchInfo: () => Promise<void> }) {
  const {
    importing,
    importResult,
    replaceData,
    setReplaceData,
    getRootProps,
    getInputProps,
    isDragActive,
  } = useBananaImport(fetchInfo);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-success" />
          <CardTitle>Banana Import</CardTitle>
        </div>
        <CardDescription>
          Laden Sie Ihre <strong>Doppelte Buchhaltung mit MWST</strong> Datei hoch — Buchungen werden importiert und das Modell automatisch trainiert.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <label className="flex items-center gap-2 text-sm cursor-pointer mb-4">
          <input
            type="checkbox"
            checked={replaceData}
            onChange={(e) => setReplaceData(e.target.checked)}
            className="rounded border-input text-brand-600 focus:ring-brand-500/20"
          />
          <Trash2 className="w-3.5 h-3.5 text-destructive" />
          <span className="text-foreground">Bestehende Trainingsdaten ersetzen</span>
        </label>

        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all",
            isDragActive
              ? "border-success/60 bg-success/8"
              : importing
              ? "border-border bg-muted/30"
              : "border-border hover:border-brand-400 hover:bg-brand-500/6"
          )}
        >
          <input {...getInputProps()} />
          {importing ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="w-10 h-10 animate-spin text-brand-600 dark:text-brand-300" />
              <p className="text-brand-600 dark:text-brand-300 font-medium">Importiert & trainiert…</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className="w-10 h-10 text-muted-foreground/40" />
              <p className="text-foreground font-medium">XLS / XLSX / CSV hierher ziehen oder klicken</p>
              <p className="text-xs text-muted-foreground">Banana Format: Buchungen mit Beschreibung, KtSoll, KtHaben, MwSt</p>
            </div>
          )}
        </div>

        {importResult && (
          <div className="mt-4 p-4 rounded-xl bg-success/10 border border-success/25">
            <h3 className="font-medium text-success flex items-center gap-2 text-sm">
              <CheckCircle className="w-4 h-4" /> Import erfolgreich
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
              <div className="text-center">
                <div className="text-xl font-bold text-success tabular-nums">{importResult.imported}</div>
                <div className="text-xs text-muted-foreground">Buchungen</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold text-success tabular-nums">{importResult.memory_entries}</div>
                <div className="text-xs text-muted-foreground">Gedächtnis</div>
              </div>
              {importResult.training && (
                <>
                  <div className="text-center">
                    <div className="text-xl font-bold text-success tabular-nums">
                      {((importResult.training.cv_accuracy ?? 0) * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-muted-foreground">Genauigkeit</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-success tabular-nums">{importResult.training.classes}</div>
                    <div className="text-xs text-muted-foreground">Klassen</div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
