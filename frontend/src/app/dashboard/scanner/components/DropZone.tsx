"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Camera, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface DropZoneProps {
  onFilesAccepted: (files: File[]) => void;
  disabled?: boolean;
  compact?: boolean;
}

export function DropZone({ onFilesAccepted, disabled, compact }: DropZoneProps) {
  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) onFilesAccepted(accepted);
  }, [onFilesAccepted]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp", ".bmp"] },
    disabled,
    multiple: true,
  });

  if (compact) {
    return (
      <div
        {...getRootProps()}
        className={cn(
          "flex items-center gap-3 rounded-lg border-2 border-dashed px-4 py-3 cursor-pointer transition-all",
          isDragActive ? "border-brand-500 bg-brand-50" : "border-border hover:border-brand-300 hover:bg-accent"
        )}
      >
        <input {...getInputProps()} />
        <Camera className="h-5 w-5 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Weitere Rechnungen hochladen</p>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={cn(
        "group relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 transition-all cursor-pointer",
        isDragActive
          ? "border-brand-500 bg-brand-50/50 scale-[1.01]"
          : "border-border hover:border-brand-300 hover:bg-accent/50",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <input {...getInputProps()} />
      <div className="rounded-2xl bg-brand-50 p-4 mb-4 group-hover:bg-brand-100 transition-colors">
        <Camera className="h-8 w-8 text-brand-600" />
      </div>
      <p className="text-base font-semibold text-foreground">
        {isDragActive ? "Dateien hier ablegen" : "Rechnung / Quittung hochladen"}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        Hierher ziehen oder klicken — JPG, PNG, WebP, BMP
      </p>
      <p className="mt-3 text-xs text-muted-foreground/60">
        AI erkennt automatisch alle Rechnungsdetails
      </p>
    </div>
  );
}
