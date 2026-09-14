import { useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";

interface Props {
  onFiles: (files: File[]) => void;
  uploading: boolean;
  progress: { done: number; total: number } | null;
}

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp";

export function BulkDropZone({ onFiles, uploading, progress }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const open = () => !uploading && inputRef.current?.click();
  const take = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length) onFiles(files);
  };
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Rechnungen hochladen"
      aria-busy={uploading}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); if (!uploading) take(e.dataTransfer.files); }}
      onClick={open}
      className={`border-2 border-dashed rounded-2xl p-6 md:p-10 text-center transition-all ${
        uploading ? "cursor-wait" : "cursor-pointer"
      } ${dragOver ? "border-brand-500 bg-brand-500/8" : "border-border hover:border-brand-400 hover:bg-accent/50"}`}
    >
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
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        aria-label="Rechnungen auswählen"
        onChange={(e) => { take(e.target.files); e.target.value = ""; }}
        className="sr-only"
        tabIndex={-1}
      />
    </div>
  );
}
