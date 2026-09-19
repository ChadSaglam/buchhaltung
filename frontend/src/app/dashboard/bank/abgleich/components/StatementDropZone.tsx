"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Loader2, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

export function StatementDropZone({ onFile, uploading }: { onFile: (file: File) => void; uploading: boolean }) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      const file = accepted[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    disabled: uploading,
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      aria-busy={uploading}
      className={cn(
        "flex items-center gap-4 rounded-2xl border-2 border-dashed p-5 transition-all",
        uploading ? "cursor-wait" : "cursor-pointer",
        isDragActive
          ? "border-brand-500 bg-brand-500/8"
          : "border-border hover:border-brand-400 hover:bg-accent/50",
      )}
    >
      <input {...getInputProps({ "aria-label": "Kontoauszug auswählen" })} />
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-500/12 text-brand-600 dark:text-brand-300">
        {uploading ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /> : <Upload className="h-5 w-5" aria-hidden="true" />}
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-foreground">
          {uploading ? "Kontoauszug wird gelesen…" : "Kontoauszug hier ablegen oder klicken"}
        </p>
        <p className="text-sm text-muted-foreground">
          UBS PDF · schon vorhandene Zeilen werden erkannt und nicht doppelt erfasst
        </p>
      </div>
    </div>
  );
}
