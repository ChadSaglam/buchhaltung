import axios from 'axios';

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export { api };
export default api;

export async function register(email: string, password: string, tenantName: string, displayName: string) {
  const res = await api.post('/api/auth/register', {
    email,
    password,
    tenant_name: tenantName,
    display_name: displayName,
  });
  return res.data;
}

export async function login(email: string, password: string) {
  const res = await api.post('/api/auth/login', { email, password });
  return res.data;
}

export async function getMe() {
  const res = await api.get('/api/auth/me');
  return res.data;
}

export async function classify(beschreibung: string, betrag: number, isCredit: boolean) {
  const res = await api.post('/api/classify/', { beschreibung, betrag, is_credit: isCredit });
  return res.data;
}

export async function logCorrection(data: {
  beschreibung: string;
  original_soll: string;
  original_haben: string;
  corrected_soll: string;
  corrected_haben: string;
  corrected_mwst_code?: string;
  corrected_mwst_pct?: string;
}) {
  const res = await api.post('/api/classify/correct', data);
  return res.data;
}

export async function trainModel() {
  const res = await api.post('/api/classify/train');
  return res.data;
}

export async function getClassifierInfo() {
  const res = await api.get('/api/classify/info');
  return res.data;
}

export async function getBookings(source?: string, limit = 500) {
  const params: Record<string, string | number> = { limit };
  if (source) params.source = source;
  const res = await api.get('/api/bookings/', { params });
  return res.data;
}

export async function createBookings(bookings: Record<string, unknown>[]) {
  const res = await api.post('/api/bookings/', bookings);
  return res.data;
}

export async function getBookingStats() {
  const res = await api.get('/api/bookings/stats');
  return res.data;
}

export async function getKontenplan() {
  const res = await api.get('/api/kontenplan/');
  return res.data;
}

export async function getKontoDefaults() {
  const res = await api.get('/api/kontenplan/defaults');
  return res.data;
}

export async function getLearningStats() {
  const res = await api.get('/api/stats/learning');
  return res.data;
}

export async function getCorrections(limit = 200) {
  const res = await api.get('/api/classify/corrections', { params: { limit } });
  return res.data;
}

export async function getMemory() {
  const res = await api.get('/api/classify/memory');
  return res.data;
}

export async function getScannerStatus() {
  const res = await api.get('/api/scanner/status');
  return res.data;
}

export async function getScannerVisionStatus(refresh = false) {
  const res = await api.get('/api/scanner/vision-status', { params: { refresh } });
  return res.data;
}

export async function extractInvoice(file: File, model?: string) {
  const form = new FormData();
  form.append('file', file);
  if (model) form.append('model', model);
  const res = await api.post('/api/scanner/extract', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function exportBanana(source?: string) {
  const params: Record<string, string> = {};
  if (source) params.source = source;
  const res = await api.get('/api/export/banana', { params, responseType: 'blob' });
  return res.data;
}

export async function exportExcel(source?: string) {
  const params: Record<string, string> = {};
  if (source) params.source = source;
  const res = await api.get('/api/export/excel', { params, responseType: 'blob' });
  return res.data;
}

export async function exportCsv(source?: string) {
  const params: Record<string, string> = {};
  if (source) params.source = source;
  const res = await api.get('/api/export/csv', { params, responseType: 'blob' });
  return res.data;
}

export async function sendExportEmail(toEmail: string, subject?: string, source?: string) {
  const res = await api.post('/api/export/email', { to_email: toEmail, subject, source });
  return res.data;
}

export async function updateKontenplan(kontenplan: Record<string, unknown>) {
  const res = await api.put('/api/kontenplan/', { kontenplan });
  return res.data;
}

export async function batchClassify(transactions: Record<string, unknown>[]) {
  const res = await api.post('/api/classify/batch', { transactions });
  return res.data;
}

export async function parsePdf(file: File) {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post('/api/pdf/parse', form);
  return res.data;
}

export async function getScannerConfig() {
  const res = await api.get('/api/scanner/config');
  return res.data;
}

export async function updateScannerConfig(data: {
  review_confidence_threshold?: number;
  pdf_ocr_enabled?: boolean;
  invoice_matching_enabled?: boolean;
  auto_classification_enabled?: boolean;
  ollama_base_url?: string;
  default_ollama_model?: string;
}) {
  const res = await api.patch('/api/scanner/config', data);
  return res.data;
}

export async function getReviewQueue() {
  const res = await api.get('/api/review/');
  return res.data;
}

export async function approveReviewItem(
  id: number,
  data?: {
    corrected_soll?: string;
    corrected_haben?: string;
    corrected_mwst_code?: string;
    corrected_mwst_pct?: string;
  }
) {
  const res = await api.post(`/api/review/${id}/approve`, data ?? {});
  return res.data;
}

export async function rejectReviewItem(id: number) {
  const res = await api.post(`/api/review/${id}/reject`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Shared booking type used by AI features (assistant, NL search, summary)
// ---------------------------------------------------------------------------
export interface Booking {
  id: number;
  datum: string;
  beschreibung: string;
  betrag: number;
  kt_soll: string;
  kt_haben: string;
  mwst_code: string;
  mwst_pct: string;
  mwst_amount: number;
  beleg?: string;
  rechnung?: string;
  source: string;
}

// ---------------------------------------------------------------------------
// AI assistant + summary (backend /api/ai → tenant Ollama, grounded on data)
// ---------------------------------------------------------------------------
export interface AiChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface AiStatus {
  ok: boolean;
  model: string;
  base_url: string;
  available_models: string[];
}

export async function aiStatus(): Promise<AiStatus> {
  const res = await api.get("/api/ai/status");
  return res.data;
}

/**
 * Stream a chat answer from the backend (Server-Sent Events).
 *
 * Calls `onToken` for each delta, `onStart` once with the resolved model, and
 * resolves when the stream ends. Rejects with a typed error object on failure
 * so the UI can show a precise reason (offline / timeout / http) plus retry.
 */
export interface AiStreamHandlers {
  onStart?: (model: string) => void;
  onToken: (token: string) => void;
  signal?: AbortSignal;
}

export async function aiChatStream(
  messages: AiChatMessage[],
  handlers: AiStreamHandlers,
): Promise<void> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const res = await fetch(`${API_URL}/api/ai/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ messages }),
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    throw { error: "http", status: res.status } as const;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      let obj: Record<string, unknown>;
      try {
        obj = JSON.parse(payload);
      } catch {
        continue;
      }
      if (obj.error) throw obj;
      if (obj.start && typeof obj.model === "string") handlers.onStart?.(obj.model);
      if (typeof obj.token === "string") handlers.onToken(obj.token);
      if (obj.done) return;
    }
  }
}

export async function aiSummary(): Promise<{ content?: string; error?: string; model?: string }> {
  const res = await api.post("/api/ai/summary");
  return res.data;
}