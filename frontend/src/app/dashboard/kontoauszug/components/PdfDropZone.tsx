"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { t } from "@/lib/i18n";

export function PdfDropZone({ onFile }: { onFile: (file: File) => void }) {
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
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "border-2 border-dashed rounded-2xl p-8 md:p-16 text-center cursor-pointer transition-all",
        isDragActive
          ? "border-brand-500 bg-brand-500/8"
          : "border-border hover:border-brand-400 hover:bg-accent/50",
      )}
    >
      <input {...getInputProps({ "aria-label": t("kontoauszug.upload") })} />
      <div className="flex justify-center mb-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-300">
          <Upload className="h-8 w-8" aria-hidden="true" />
        </div>
      </div>
      <p className="text-foreground font-semibold text-base">{t("kontoauszug.upload")}</p>
      <p className="text-muted-foreground text-sm mt-2">UBS Kontoauszug (.pdf)</p>
    </div>
  );
}
