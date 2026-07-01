import { NextRequest, NextResponse } from "next/server";

/**
 * AI assistant proxy → Ollama.
 *
 * Forwards a chat request to a local/remote Ollama instance (/api/chat) and
 * returns the assistant message. If Ollama is unreachable or misconfigured,
 * responds with `{ fallback: true }` and a friendly German message so the UI
 * can degrade gracefully instead of erroring.
 *
 * Env:
 *   OLLAMA_BASE_URL   default http://localhost:11434
 *   OLLAMA_CHAT_MODEL default llama3.1
 */
export const runtime = "nodejs";

const OLLAMA_BASE_URL = (process.env.OLLAMA_BASE_URL || "http://localhost:11434").replace(/\/$/, "");
const OLLAMA_CHAT_MODEL = process.env.OLLAMA_CHAT_MODEL || "llama3.1";

interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

const SYSTEM_PROMPT = `Du bist der AI-Assistent einer Schweizer Buchhaltungs-App.
Beantworte Fragen zu Buchungen, Konten (Kontenplan), MwSt/VAT und Auswertungen präzise und knapp auf Deutsch.
Du erhältst ggf. einen kompakten Kontext mit aggregierten Buchungsdaten (JSON). Nutze ausschliesslich diesen Kontext für Zahlen.
Wenn dir Daten fehlen, sage das ehrlich und schlage vor, welche Seite (Kontoauszug, Scanner, Modell) weiterhilft.
Erfinde keine Beträge. Formatiere Beträge als CHF mit zwei Nachkommastellen.`;

export async function POST(req: NextRequest) {
  let body: { messages?: ChatMessage[]; context?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const messages = Array.isArray(body.messages) ? body.messages : [];
  if (messages.length === 0) {
    return NextResponse.json({ error: "no_messages" }, { status: 400 });
  }

  const contextBlock = body.context
    ? `\n\nKontext (aggregierte Buchungsdaten als JSON):\n${JSON.stringify(body.context).slice(0, 6000)}`
    : "";

  const payload = {
    model: OLLAMA_CHAT_MODEL,
    stream: false,
    messages: [
      { role: "system", content: SYSTEM_PROMPT + contextBlock },
      ...messages,
    ],
    options: { temperature: 0.2 },
  };

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45_000);
    const res = await fetch(`${OLLAMA_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok) {
      return NextResponse.json(
        { fallback: true, message: fallbackMessage() },
        { status: 200 }
      );
    }
    const data = await res.json();
    const content: string = data?.message?.content?.trim() || "";
    if (!content) {
      return NextResponse.json({ fallback: true, message: fallbackMessage() }, { status: 200 });
    }
    return NextResponse.json({ content, model: OLLAMA_CHAT_MODEL });
  } catch {
    return NextResponse.json({ fallback: true, message: fallbackMessage() }, { status: 200 });
  }
}

function fallbackMessage(): string {
  return "Der AI-Assistent ist gerade nicht erreichbar (Ollama offline oder Modell nicht geladen). Du kannst weiterhin die Schnellsuche und die Auswertungen im Dashboard nutzen.";
}
