"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Loader2, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onFiles: (files: File[]) => void;
  uploading: boolean;
  progress: { done: number; total: number } | null;
}

export function BulkDropZone({ onFiles, uploading, progress }: Props) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) onFiles(accepted);
    },
    [onFiles],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/*": [".jpg", ".jpeg", ".png", ".webp"],
    },
    disabled: uploading,
    multiple: true,
  });

  return (
    <div
      {...getRootProps()}
      aria-busy={uploading}
      className={cn(
        "border-2 border-dashed rounded-2xl p-6 md:p-10 text-center transition-all",
        uploading ? "cursor-wait" : "cursor-pointer",
        isDragActive
          ? "border-brand-500 bg-brand-500/8"
          : "border-border hover:border-brand-400 hover:bg-accent/50",
      )}
    >
      <input {...getInputProps({ "aria-label": "Rechnungen auswählen" })} />
      <div className="flex justify-center mb-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-300">
          {uploading ? <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" /> : <Upload className="h-6 w-6" aria-hidden="true" />}
        </div>
      </div>
      {uploading && progress ? (
        <p className="text-foreground font-semibold" role="status" aria-live="polite">
          {progress.done} / {progress.total} Dateien verarbeitet…
        </p>
      ) : (
        <>
          <p className="text-foreground font-semibold">Rechnungen hier ablegen oder klicken — auch 50 auf einmal</p>
          <p className="text-muted-foreground text-sm mt-1">PDF, JPG, PNG · QR-Rechnungen werden exakt gelesen, der Rest per Vision/OCR</p>
        </>
      )}
    </div>
  );
}
