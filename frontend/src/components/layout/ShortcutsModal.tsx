"use client";
import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Keyboard, X } from "lucide-react";
import { useUiStore } from "@/lib/ui-store";
import { useCommandStore } from "@/lib/command-store";
import { useFocusTrap } from "@/hooks/useFocusTrap";

interface Shortcut {
  keys: string[];
  label: string;
}

const GROUPS: { title: string; items: Shortcut[] }[] = [
  {
    title: "Allgemein",
    items: [
      { keys: ["⌘", "K"], label: "Befehlspalette / Suche öffnen" },
      { keys: ["?"], label: "Diese Übersicht anzeigen" },
      { keys: ["A"], label: "AI-Assistent umschalten" },
      { keys: ["Esc"], label: "Dialog / Overlay schliessen" },
    ],
  },
  {
    title: "Befehlspalette",
    items: [
      { keys: ["↑", "↓"], label: "Zwischen Einträgen navigieren" },
      { keys: ["↵"], label: "Auswahl ausführen" },
    ],
  },
];

export function ShortcutsModal() {
  const { shortcutsOpen, setShortcutsOpen, toggleShortcuts, toggleAssistant } = useUiStore();
  const dialogRef = useRef<HTMLDivElement>(null);
  // Esc closes, Tab stays inside, focus returns to the opener.
  useFocusTrap(shortcutsOpen, () => setShortcutsOpen(false), dialogRef);

  // Global hotkeys: "?" opens shortcuts, "A" toggles assistant — but only when
  // the user isn't typing in a field and the command palette isn't open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (typing) return;
      if (useCommandStore.getState().open) return;

      if (e.key === "?") {
        e.preventDefault();
        toggleShortcuts();
      } else if (e.key.toLowerCase() === "a" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        toggleAssistant();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleShortcuts, toggleAssistant]);

  return (
    <AnimatePresence>
      {shortcutsOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
        >
          <div className="absolute inset-0 bg-black/45 backdrop-blur-sm" onClick={() => setShortcutsOpen(false)} aria-hidden="true" />
          <motion.div
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            ref={dialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="shortcuts-title"
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 dark:text-brand-300">
                  <Keyboard className="h-4 w-4" aria-hidden="true" />
                </span>
                <h2 id="shortcuts-title" className="text-sm font-semibold text-foreground">Tastaturkürzel</h2>
              </div>
              <button
                type="button"
                onClick={() => setShortcutsOpen(false)}
                aria-label="Schliessen"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <div className="space-y-5 p-5">
              {GROUPS.map((g) => (
                <div key={g.title}>
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {g.title}
                  </p>
                  <ul className="space-y-1.5">
                    {g.items.map((s) => (
                      <li key={s.label} className="flex items-center justify-between gap-4">
                        <span className="text-sm text-foreground">{s.label}</span>
                        <span className="flex shrink-0 items-center gap-1">
                          {s.keys.map((k) => (
                            <kbd
                              key={k}
                              className="min-w-6 rounded-md border border-border bg-muted px-1.5 py-0.5 text-center text-[11px] font-medium text-muted-foreground"
                            >
                              {k}
                            </kbd>
                          ))}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
