import { NextRequest, NextResponse } from "next/server";

/**
 * AI monthly summary / anomaly narration → Ollama.
 *
 * Receives already-computed monthly aggregates + detected anomalies and asks
 * Ollama to produce a short German narrative. Falls back to `{ fallback: true }`
 * when Ollama is unavailable so the UI can render the deterministic stats alone.
 */
export const runtime = "nodejs";

const OLLAMA_BASE_URL = (process.env.OLLAMA_BASE_URL || "http://localhost:11434").replace(/\/$/, "");
const OLLAMA_CHAT_MODEL = process.env.OLLAMA_CHAT_MODEL || "llama3.1";

export async function POST(req: NextRequest) {
  let body: { stats?: unknown; anomalies?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const prompt = `Fasse die folgende Monatsauswertung einer Schweizer Buchhaltung in 3–5 kurzen Sätzen auf Deutsch zusammen.
Hebe auffällige Ausreisser hervor, bleibe sachlich und erfinde keine Zahlen.

Kennzahlen (JSON):
${JSON.stringify(body.stats ?? {}).slice(0, 4000)}

Erkannte Auffälligkeiten (JSON):
${JSON.stringify(body.anomalies ?? []).slice(0, 3000)}`;

  const payload = {
    model: OLLAMA_CHAT_MODEL,
    stream: false,
    messages: [
      { role: "system", content: "Du bist ein präziser Buchhaltungs-Analyst. Antworte knapp auf Deutsch." },
      { role: "user", content: prompt },
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
    if (!res.ok) return NextResponse.json({ fallback: true }, { status: 200 });
    const data = await res.json();
    const content: string = data?.message?.content?.trim() || "";
    if (!content) return NextResponse.json({ fallback: true }, { status: 200 });
    return NextResponse.json({ content, model: OLLAMA_CHAT_MODEL });
  } catch {
    return NextResponse.json({ fallback: true }, { status: 200 });
  }
}
