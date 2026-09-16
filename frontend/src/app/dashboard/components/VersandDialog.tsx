"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, Mail, Paperclip, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { versandGrund, versandLabel, type VersandEntwurf } from "@/app/dashboard/rechnungen/versand";

interface Props {
  draft: VersandEntwurf | null;
  sending: boolean;
  onClose: () => void;
  onSend: (edited: { empfaenger: string; subject: string; text: string }) => void;
}

/**
 * The invoice mail, before it goes out (B-79). Same contract as the Mahnung
 * dialog: everything is editable, nothing is sent until the owner says so.
 */
export function VersandDialog({ draft, sending, onClose, onSend }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [empfaenger, setEmpfaenger] = useState("");
  const [subject, setSubject] = useState("");
  const [text, setText] = useState("");
  useFocusTrap(Boolean(draft), onClose, dialogRef);

  useEffect(() => {
    if (!draft) return;
    setEmpfaenger(draft.empfaenger);
    setSubject(draft.subject);
    setText(draft.text);
  }, [draft]);

  const grund = versandGrund(draft);
  const kannSenden = Boolean(draft?.bereit || empfaenger.trim()) && !sending;

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
            aria-labelledby="versand-title"
            className="relative flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
              <div className="min-w-0">
                <h2 id="versand-title" className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Mail className="h-4 w-4" aria-hidden="true" /> Rechnung per E-Mail
                </h2>
                <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
                  <Paperclip className="h-3 w-3 shrink-0" aria-hidden="true" />
                  {draft.dateiname}
                  {draft.schon_gesendet_am && <> · zuletzt gesendet {draft.schon_gesendet_am}</>}
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Schliessen"
                className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
              {grund && (
                <p role="status" className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-foreground">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" aria-hidden="true" />
                  {grund}
                </p>
              )}

              <label className="block">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">An</span>
                <input
                  type="email"
                  value={empfaenger}
                  onChange={(e) => setEmpfaenger(e.target.value)}
                  placeholder="kunde@firma.ch"
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20"
                />
              </label>

              <label className="block">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Betreff</span>
                <input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20"
                />
              </label>

              <label className="block">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Text</span>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={12}
                  className="mt-1 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 font-sans text-sm leading-relaxed text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20"
                />
              </label>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-5 py-3">
              <p className="text-xs text-muted-foreground">Die Rechnung hängt als PDF an.</p>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={onClose}>
                  Abbrechen
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  loading={sending}
                  disabled={!kannSenden}
                  onClick={() => onSend({ empfaenger, subject, text })}
                >
                  {versandLabel(draft)}
                </Button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
