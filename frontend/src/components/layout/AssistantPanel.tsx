"use client";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Bot, X, Send, Sparkles, Loader2, User as UserIcon } from "lucide-react";
import { useUiStore } from "@/lib/ui-store";
import { aiChat, getBookings, getBookingStats, type AiChatMessage, type Booking } from "@/lib/api";
import { monthlyStats } from "@/lib/booking-analytics";
import { cn } from "@/lib/utils";

interface ChatEntry {
  role: "user" | "assistant";
  content: string;
  fallback?: boolean;
}

const SUGGESTIONS = [
  "Wie hoch waren meine Ausgaben letzten Monat?",
  "Welche Buchungen betreffen Konto 6500?",
  "Erkläre mir den MwSt-Code auf meinen Rechnungen.",
  "Gibt es auffällige Transaktionen?",
];

/** Build a compact, token-bounded context object from the tenant's bookings. */
async function buildContext(): Promise<unknown> {
  try {
    const [bookings, stats] = await Promise.all([
      getBookings(undefined, 300).catch(() => [] as Booking[]),
      getBookingStats().catch(() => null),
    ]);
    const list = (bookings as Booking[]) ?? [];
    return {
      stats,
      monthly: monthlyStats(list).slice(0, 6),
      recent: list.slice(0, 40).map((b) => ({
        datum: b.datum,
        beschreibung: b.beschreibung,
        betrag: b.betrag,
        soll: b.kt_soll,
        haben: b.kt_haben,
        mwst: b.mwst_code,
      })),
    };
  } catch {
    return null;
  }
}

export function AssistantPanel() {
  const { assistantOpen, setAssistantOpen } = useUiStore();
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (assistantOpen) setTimeout(() => inputRef.current?.focus(), 120);
  }, [assistantOpen]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (!assistantOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAssistantOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [assistantOpen, setAssistantOpen]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || sending) return;
    setInput("");
    const history = [...messages, { role: "user" as const, content: q }];
    setMessages(history);
    setSending(true);
    try {
      const context = await buildContext();
      const payload: AiChatMessage[] = history.map((m) => ({ role: m.role, content: m.content }));
      const res = await aiChat(payload, context);
      const content = res.content || res.message || "Keine Antwort erhalten.";
      setMessages((prev) => [...prev, { role: "assistant", content, fallback: !!res.fallback }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Es ist ein Fehler aufgetreten. Bitte später erneut versuchen.", fallback: true },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <AnimatePresence>
      {assistantOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setAssistantOpen(false)}
            className="fixed inset-0 z-[90] bg-black/40 backdrop-blur-sm"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 38 }}
            role="dialog"
            aria-modal="true"
            aria-label="AI-Assistent"
            className="fixed inset-y-0 right-0 z-[95] flex w-full max-w-md flex-col border-l border-border bg-surface shadow-2xl"
          >
            {/* Header */}
            <div className="flex h-[var(--topbar-height)] shrink-0 items-center gap-2.5 border-b border-border px-4">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 dark:text-brand-300">
                <Bot className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground">AI-Assistent</p>
                <p className="text-[11px] text-muted-foreground">Fragen zu Buchungen, Konten & MwSt</p>
              </div>
              <button
                onClick={() => setAssistantOpen(false)}
                aria-label="Assistent schliessen"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
              {messages.length === 0 && (
                <div className="space-y-4">
                  <div className="rounded-xl border border-border bg-card p-4">
                    <div className="mb-2 flex items-center gap-2 text-brand-600 dark:text-brand-300">
                      <Sparkles className="h-4 w-4" />
                      <p className="text-sm font-semibold">Womit kann ich helfen?</p>
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      Ich beantworte Fragen zu deinen Buchungen, Konten und der MwSt. Antworten basieren auf deinen
                      gespeicherten Daten. Der Dienst nutzt dein lokales Ollama-Modell.
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        className="w-full rounded-lg border border-border bg-card px-3 py-2 text-left text-sm text-foreground transition-colors hover:border-border-strong hover:bg-accent"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) => (
                <div key={i} className={cn("flex gap-2.5", m.role === "user" && "flex-row-reverse")}>
                  <span
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                      m.role === "user" ? "bg-muted text-muted-foreground" : "bg-brand-500/12 text-brand-600 dark:text-brand-300"
                    )}
                  >
                    {m.role === "user" ? <UserIcon className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
                  </span>
                  <div
                    className={cn(
                      "max-w-[80%] whitespace-pre-wrap rounded-xl px-3 py-2 text-sm leading-relaxed",
                      m.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : m.fallback
                          ? "border border-warning/30 bg-warning/10 text-foreground"
                          : "border border-border bg-card text-foreground"
                    )}
                  >
                    {m.content}
                  </div>
                </div>
              ))}

              {sending && (
                <div className="flex gap-2.5">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 dark:text-brand-300">
                    <Bot className="h-3.5 w-3.5" />
                  </span>
                  <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-sm text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Denke nach…
                  </div>
                </div>
              )}
            </div>

            {/* Composer */}
            <div className="shrink-0 border-t border-border p-3">
              <div className="flex items-end gap-2 rounded-xl border border-border bg-card p-2 focus-within:border-border-strong focus-within:ring-2 focus-within:ring-ring/30">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send(input);
                    }
                  }}
                  rows={1}
                  placeholder="Frage stellen…"
                  className="max-h-32 flex-1 resize-none bg-transparent px-1.5 py-1 text-sm text-foreground outline-none placeholder:text-muted-foreground"
                />
                <button
                  onClick={() => send(input)}
                  disabled={!input.trim() || sending}
                  aria-label="Senden"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-[filter] hover:brightness-110 disabled:opacity-40"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
              <p className="mt-1.5 px-1 text-[11px] text-muted-foreground">
                Enter zum Senden · Shift+Enter für Zeilenumbruch
              </p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
