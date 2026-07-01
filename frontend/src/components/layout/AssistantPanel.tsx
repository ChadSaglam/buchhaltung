"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Bot, X, Send, Sparkles, Loader2, User as UserIcon, Square,
  RotateCcw, Wifi, WifiOff, AlertTriangle, Trash2,
} from "lucide-react";
import { useUiStore } from "@/lib/ui-store";
import { aiChatStream, aiStatus, type AiChatMessage, type AiStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChatEntry {
  role: "user" | "assistant";
  content: string;
  error?: string;
}

const SUGGESTIONS = [
  "Wie hoch waren meine Ausgaben letzten Monat?",
  "Welche Buchungen betreffen Konto 6500?",
  "Erkläre mir den MwSt-Code auf meinen Rechnungen.",
  "Gibt es auffällige Transaktionen?",
];

function errorMessage(err: unknown): string {
  const e = err as { error?: string; status?: number };
  if (e?.error === "connect")
    return "Ollama ist nicht erreichbar. Läuft `ollama serve` und stimmt die Basis-URL in den Scanner-Einstellungen?";
  if (e?.error === "timeout")
    return "Zeitüberschreitung — das Modell hat zu lange gebraucht. Versuche eine kürzere Frage oder ein kleineres Modell.";
  if (e?.error === "empty")
    return "Das Modell hat keine Antwort geliefert. Ist ein Text-Modell in den Scanner-Einstellungen gewählt?";
  if (typeof e?.status === "number")
    return `Serverfehler (HTTP ${e.status}). Bitte später erneut versuchen.`;
  return "Unerwarteter Fehler. Bitte später erneut versuchen.";
}

export function AssistantPanel() {
  const { assistantOpen, setAssistantOpen } = useUiStore();
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<AiStatus | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshStatus = useCallback(() => {
    aiStatus().then(setStatus).catch(() => setStatus({ ok: false, model: "", base_url: "", available_models: [] }));
  }, []);

  useEffect(() => {
    if (assistantOpen) {
      setTimeout(() => inputRef.current?.focus(), 120);
      refreshStatus();
    }
  }, [assistantOpen, refreshStatus]);

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

  const runChat = useCallback(async (history: ChatEntry[]) => {
    setSending(true);
    const controller = new AbortController();
    abortRef.current = controller;
    // Push an empty assistant entry we stream into.
    setMessages([...history, { role: "assistant", content: "" }]);
    const payload: AiChatMessage[] = history.map((m) => ({ role: m.role, content: m.content }));
    try {
      await aiChatStream(payload, {
        signal: controller.signal,
        onToken: (t) =>
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant") next[next.length - 1] = { ...last, content: last.content + t };
            return next;
          }),
      });
      refreshStatus();
    } catch (err) {
      if ((err as Error)?.name === "AbortError") {
        // User stopped — keep partial content.
      } else {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          const msg = errorMessage(err);
          if (last?.role === "assistant" && !last.content) next[next.length - 1] = { role: "assistant", content: msg, error: msg };
          else next.push({ role: "assistant", content: msg, error: msg });
          return next;
        });
        refreshStatus();
      }
    } finally {
      setSending(false);
      abortRef.current = null;
    }
  }, [refreshStatus]);

  const send = (text: string) => {
    const q = text.trim();
    if (!q || sending) return;
    setInput("");
    runChat([...messages, { role: "user", content: q }]);
  };

  const retryLast = () => {
    // Drop trailing assistant error, resend from last user message.
    const trimmed = [...messages];
    while (trimmed.length && trimmed[trimmed.length - 1].role === "assistant") trimmed.pop();
    if (trimmed.length) runChat(trimmed);
  };

  const stop = () => abortRef.current?.abort();
  const clear = () => { stop(); setMessages([]); };

  const lastIsError = messages.length > 0 && !!messages[messages.length - 1].error;

  return (
    <AnimatePresence>
      {assistantOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setAssistantOpen(false)}
            className="fixed inset-0 z-[90] bg-black/40 backdrop-blur-sm"
          />
          <motion.aside
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 38 }}
            role="dialog" aria-modal="true" aria-label="AI-Assistent"
            className="fixed inset-y-0 right-0 z-[95] flex w-full max-w-md flex-col border-l border-border bg-surface shadow-2xl"
          >
            {/* Header */}
            <div className="flex h-[var(--topbar-height)] shrink-0 items-center gap-2.5 border-b border-border px-4">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/12 text-brand-600 dark:text-brand-300">
                <Bot className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground">AI-Assistent</p>
                <StatusLine status={status} />
              </div>
              {messages.length > 0 && (
                <button onClick={clear} title="Verlauf leeren" aria-label="Verlauf leeren"
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
              <button onClick={() => setAssistantOpen(false)} aria-label="Assistent schliessen"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Offline banner */}
            {status && !status.ok && (
              <div className="flex items-start gap-2 border-b border-warning/30 bg-warning/10 px-4 py-2.5 text-xs text-foreground">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                <span>
                  Ollama offline. Starte den Dienst mit <code className="rounded bg-muted px-1">ollama serve</code> und
                  prüfe die Basis-URL unter Scanner-Einstellungen.
                </span>
              </div>
            )}

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
                      gespeicherten Daten und dem Kontenplan.
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    {SUGGESTIONS.map((s) => (
                      <button key={s} onClick={() => send(s)}
                        className="w-full rounded-lg border border-border bg-card px-3 py-2 text-left text-sm text-foreground transition-colors hover:border-border-strong hover:bg-accent">
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) => {
                const streaming = sending && i === messages.length - 1 && m.role === "assistant";
                return (
                  <div key={i} className={cn("flex gap-2.5", m.role === "user" && "flex-row-reverse")}>
                    <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                      m.role === "user" ? "bg-muted text-muted-foreground" : "bg-brand-500/12 text-brand-600 dark:text-brand-300")}>
                      {m.role === "user" ? <UserIcon className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
                    </span>
                    <div className={cn("max-w-[80%] whitespace-pre-wrap rounded-xl px-3 py-2 text-sm leading-relaxed",
                      m.role === "user" ? "bg-primary text-primary-foreground"
                        : m.error ? "border border-warning/30 bg-warning/10 text-foreground"
                          : "border border-border bg-card text-foreground")}>
                      {m.content || (streaming ? <span className="inline-flex items-center gap-1.5 text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Denke nach…</span> : "")}
                      {streaming && m.content && <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse rounded-sm bg-brand-500 align-middle" />}
                    </div>
                  </div>
                );
              })}

              {lastIsError && !sending && (
                <button onClick={retryLast}
                  className="mx-auto flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground">
                  <RotateCcw className="h-3.5 w-3.5" /> Erneut versuchen
                </button>
              )}
            </div>

            {/* Composer */}
            <div className="shrink-0 border-t border-border p-3">
              <div className="flex items-end gap-2 rounded-xl border border-border bg-card p-2 focus-within:border-border-strong focus-within:ring-2 focus-within:ring-ring/30">
                <textarea
                  ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
                  rows={1} placeholder="Frage stellen…"
                  className="max-h-32 flex-1 resize-none bg-transparent px-1.5 py-1 text-sm text-foreground outline-none placeholder:text-muted-foreground"
                />
                {sending ? (
                  <button onClick={stop} aria-label="Stopp"
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground transition-colors hover:bg-accent">
                    <Square className="h-3.5 w-3.5" />
                  </button>
                ) : (
                  <button onClick={() => send(input)} disabled={!input.trim()} aria-label="Senden"
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-[filter] hover:brightness-110 disabled:opacity-40">
                    <Send className="h-4 w-4" />
                  </button>
                )}
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

function StatusLine({ status }: { status: AiStatus | null }) {
  if (!status) {
    return <p className="flex items-center gap-1 text-[11px] text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" /> Prüfe Verbindung…</p>;
  }
  if (status.ok) {
    return (
      <p className="flex items-center gap-1 text-[11px] text-success" title={`Modell: ${status.model} · ${status.base_url}`}>
        <Wifi className="h-3 w-3" /> Verbunden · {status.model || "Modell"}
      </p>
    );
  }
  return <p className="flex items-center gap-1 text-[11px] text-destructive"><WifiOff className="h-3 w-3" /> Ollama offline</p>;
}
