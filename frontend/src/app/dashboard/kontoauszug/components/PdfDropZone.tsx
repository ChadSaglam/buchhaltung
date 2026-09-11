import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { t } from "@/lib/i18n";

export function PdfDropZone({ onFile }: { onFile: (file: File) => void }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const open = () => inputRef.current?.click();
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={t("kontoauszug.upload")}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) onFile(f); }}
      onClick={open}
      className={`border-2 border-dashed rounded-2xl p-8 md:p-16 text-center cursor-pointer transition-all ${
        dragOver ? "border-brand-500 bg-brand-500/8" : "border-border hover:border-brand-400 hover:bg-accent/50"
      }`}
    >
      <div className="flex justify-center mb-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-300">
          <Upload className="h-8 w-8" aria-hidden="true" />
        </div>
      </div>
      <p className="text-foreground font-semibold text-base">{t("kontoauszug.upload")}</p>
      <p className="text-muted-foreground text-sm mt-2">UBS Kontoauszug (.pdf)</p>
      <input
        ref={inputRef}
        id="pdf-input"
        type="file"
        accept=".pdf"
        aria-label={t("kontoauszug.upload")}
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        className="sr-only"
        tabIndex={-1}
      />
    </div>
  );
}
