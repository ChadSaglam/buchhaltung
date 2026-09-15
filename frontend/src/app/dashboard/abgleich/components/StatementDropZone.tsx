import { useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";

export function StatementDropZone({ onFile, uploading }: { onFile: (file: File) => void; uploading: boolean }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const open = () => !uploading && inputRef.current?.click();
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Kontoauszug hochladen"
      aria-busy={uploading}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f && !uploading) onFile(f); }}
      onClick={open}
      className={`flex items-center gap-4 rounded-2xl border-2 border-dashed p-5 transition-all ${
        uploading ? "cursor-wait" : "cursor-pointer"
      } ${dragOver ? "border-brand-500 bg-brand-500/8" : "border-border hover:border-brand-400 hover:bg-accent/50"}`}
    >
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
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        aria-label="Kontoauszug auswählen"
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onFile(f); }}
        className="sr-only"
        tabIndex={-1}
      />
    </div>
  );
}
