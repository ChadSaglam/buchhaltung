import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import api, { API_URL } from "@/lib/api";
import { toAppError } from "@/lib/errors";
import type { OllamaStatus, ExtractedInvoice } from "../types";
import type { PipelineStep } from "../components/ProcessingOverlay";

function normalizeInvoicePayload(payload: unknown): ExtractedInvoice | null {
  if (!payload || typeof payload !== "object") return null;
  const maybeWrapped = payload as { data?: ExtractedInvoice };
  if (maybeWrapped.data && typeof maybeWrapped.data === "object") return maybeWrapped.data;
  return payload as ExtractedInvoice;
}

/** Reads an SSE body block by block; `onEvent` gets every parsed event. */
async function readSse(body: ReadableStream<Uint8Array>, onEvent: (type: string, payload: unknown) => void) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const eventMatch = block.match(/^event: (.+)$/m);
      const dataMatch = block.match(/^data: (.+)$/m);
      if (eventMatch && dataMatch) onEvent(eventMatch[1], JSON.parse(dataMatch[1]));
    }
  }
}

export function useScanner() {
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState("");
  const [processing, setProcessing] = useState(false);
  const [processingFile, setProcessingFile] = useState("");
  const [invoices, setInvoices] = useState<ExtractedInvoice[]>([]);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [elapsed, setElapsed] = useState(0);
  // The last file that failed, so the error state can offer a retry.
  const [failure, setFailure] = useState<{ error: unknown; file: File } | null>(null);

  useEffect(() => {
    api
      .get("/api/scanner/vision-status")
      .then((res) => {
        setStatus(res.data);
        if (res.data.best_vision) setSelectedModel(res.data.best_vision);
        else if (res.data.models?.[0]) setSelectedModel(res.data.models[0].name);
      })
      .catch(() => setStatus({ ok: false }))
      .finally(() => setStatusLoading(false));
  }, []);

  const extractOne = useCallback(
    async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      if (selectedModel) form.append("model", selectedModel);
      const token = localStorage.getItem("token") || "";
      const response = await fetch(`${API_URL}/api/scanner/extract`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw toAppError({ response: { status: response.status, data } });
      }
      const accept = (payload: unknown) => {
        const invoice = normalizeInvoicePayload(payload);
        if (!invoice) throw new Error("Ungültige Scanner-Antwort");
        setInvoices((prev) => [...prev, invoice]);
        toast.success(`${file.name} erkannt`);
      };
      if ((response.headers.get("content-type") || "").includes("text/event-stream") && response.body) {
        await readSse(response.body, (type, payload) => {
          if (type === "step") setPipelineSteps((prev) => [...prev, payload as PipelineStep]);
          else if (type === "result") accept(payload);
          else if (type === "error") throw new Error((payload as { message?: string }).message || "Scanner-Fehler");
        });
      } else {
        accept(await response.json());
      }
    },
    [selectedModel]
  );

  const processFiles = useCallback(
    async (files: File[]) => {
      setFailure(null);
      for (const file of files) {
        setProcessing(true);
        setProcessingFile(file.name);
        setPipelineSteps([]);
        setElapsed(0);
        const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
        try {
          await extractOne(file);
        } catch (e) {
          setFailure({ error: e, file });
        } finally {
          clearInterval(timer);
        }
      }
      setProcessing(false);
      setProcessingFile("");
      setPipelineSteps([]);
    },
    [extractOne]
  );

  const retry = () => failure && processFiles([failure.file]);
  const updateInvoice = (index: number, updated: ExtractedInvoice) =>
    setInvoices((prev) => prev.map((inv, i) => (i === index ? updated : inv)));

  const isCloud =
    selectedModel.endsWith(":cloud") ||
    selectedModel.endsWith("-cloud") ||
    status?.models?.find((m) => m.name === selectedModel)?.kind === "cloud";

  return {
    status, statusLoading, selectedModel, setSelectedModel, isCloud,
    processing, processingFile, pipelineSteps, elapsed,
    invoices, updateInvoice, processFiles,
    failure, retry,
  };
}
