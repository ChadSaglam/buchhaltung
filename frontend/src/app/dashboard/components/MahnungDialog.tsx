"use client";

import { useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Copy, FileDown, Printer, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import type { MahnungDraft } from "@/lib/offene-posten";

interface Props {
  draft: MahnungDraft | null;
  recording: boolean;
  onClose: () => void;
  onRecord: () => void;
  onPrint: (draft: MahnungDraft) => void;
  /** The letter as a file — what actually goes in the envelope. */
  onPdf: (draft: MahnungDraft) => void;
}

/** The draft the owner reads before anything leaves the house. */
export function MahnungDialog({ draft, recording, onClose, onRecord, onPrint, onPdf }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  useFocusTrap(Boolean(draft), onClose, dialogRef);

  const copy = async () => {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.text}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <AnimatePresence>
      {draft && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div className="absolute inset-0 bg-black/45 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
          <motion.div
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            ref={dialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="mahnung-title"
            className="relative flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
              <div className="min-w-0">
                <h2 id="mahnung-title" className="text-sm font-semibold text-foreground">
                  {draft.stufe_label}
                </h2>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">
                  An {draft.empfaenger || "—"}
                  {draft.empfaenger_email ? ` · ${draft.empfaenger_email}` : " · keine E-Mail erfasst"}
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Schliessen"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Betreff</p>
              <p className="mt-1 text-sm font-medium text-foreground">{draft.subject}</p>
              <p className="mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">Text</p>
              <pre className="mt-1 whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                {draft.text}
              </pre>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-5 py-3">
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" icon={copied ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />} onClick={copy}>
                  {copied ? "Kopiert" : "Text kopieren"}
                </Button>
                <Button size="sm" variant="secondary" icon={<FileDown className="h-3.5 w-3.5" aria-hidden="true" />} onClick={() => onPdf(draft)}>
                  PDF
                </Button>
                <Button size="sm" variant="ghost" icon={<Printer className="h-3.5 w-3.5" aria-hidden="true" />} onClick={() => onPrint(draft)}>
                  Druckvorschau
                </Button>
              </div>
              <Button size="sm" variant="primary" loading={recording} onClick={onRecord}>
                Als versendet erfassen
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
