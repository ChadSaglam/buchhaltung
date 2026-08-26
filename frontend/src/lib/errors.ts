/**
 * One place that turns any failure into something a human can act on.
 *
 * The backend returns a uniform envelope:
 *   { "error": { "code": "...", "message": "...", "request_id": "..." } }
 * Anything else (network down, CORS, timeout, HTML error page) is normalised
 * here too, so the UI never has to guess.
 */

export type AppError = {
  /** Short machine code, e.g. `http_404`, `offline`, `validation_error`. */
  code: string;
  /** German, user-facing, actionable. Safe to render directly. */
  message: string;
  /** HTTP status when there was a response. */
  status?: number;
  /** Correlation id from `X-Request-ID` — quote this in a bug report. */
  requestId?: string;
  /** Field-level problems from a 422. */
  fields?: { field: string; message: string }[];
  /** Whether retrying the same request could plausibly succeed. */
  retryable: boolean;
};

const BY_STATUS: Record<number, string> = {
  400: "Die Anfrage war ungültig. Bitte prüfe deine Eingaben.",
  401: "Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.",
  403: "Dafür fehlt dir die Berechtigung.",
  404: "Nicht gefunden — der Eintrag existiert nicht (mehr).",
  409: "Das kollidiert mit einem bestehenden Eintrag.",
  413: "Die Datei ist zu gross.",
  415: "Dieses Dateiformat wird nicht unterstützt.",
  422: "Die Eingaben sind unvollständig oder ungültig.",
  429: "Zu viele Anfragen. Bitte einen Moment warten.",
  500: "Serverfehler. Wir konnten die Anfrage nicht abschliessen.",
  502: "Der Server ist gerade nicht erreichbar.",
  503: "Der Dienst ist vorübergehend nicht verfügbar.",
  504: "Zeitüberschreitung — der Server hat zu lange gebraucht.",
};

const RETRYABLE = new Set([408, 429, 500, 502, 503, 504]);

function pickEnvelope(data: unknown): Partial<AppError> | null {
  if (!data || typeof data !== "object") return null;
  const err = (data as { error?: unknown }).error;
  if (!err || typeof err !== "object") {
    const detail = (data as { detail?: unknown }).detail;
    return typeof detail === "string" ? { message: detail } : null;
  }
  const e = err as Record<string, unknown>;
  return {
    code: typeof e.code === "string" ? e.code : undefined,
    message: typeof e.message === "string" ? e.message : undefined,
    requestId: typeof e.request_id === "string" ? e.request_id : undefined,
    fields: Array.isArray(e.fields) ? (e.fields as AppError["fields"]) : undefined,
  };
}

export function toAppError(err: unknown): AppError {
  // Aborted by us (navigation, new keystroke) — not a real failure.
  if (err instanceof DOMException && err.name === "AbortError") {
    return { code: "aborted", message: "Abgebrochen.", retryable: true };
  }

  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return {
      code: "offline",
      message: "Keine Internetverbindung. Änderungen wurden nicht gespeichert.",
      retryable: true,
    };
  }

  const anyErr = err as {
    response?: { status?: number; data?: unknown; headers?: Record<string, string> };
    code?: string;
    message?: string;
  };

  const response = anyErr?.response;
  if (response?.status) {
    const status = response.status;
    const env = pickEnvelope(response.data) ?? {};
    return {
      code: env.code ?? `http_${status}`,
      message: env.message ?? BY_STATUS[status] ?? "Die Anfrage ist fehlgeschlagen.",
      status,
      requestId: env.requestId ?? response.headers?.["x-request-id"],
      fields: env.fields,
      retryable: RETRYABLE.has(status),
    };
  }

  if (anyErr?.code === "ECONNABORTED" || /timeout/i.test(anyErr?.message ?? "")) {
    return { code: "timeout", message: "Zeitüberschreitung. Bitte erneut versuchen.", retryable: true };
  }

  if (anyErr?.code === "ERR_NETWORK") {
    return {
      code: "network",
      message: "Server nicht erreichbar. Läuft das Backend?",
      retryable: true,
    };
  }

  return {
    code: "unknown",
    message: anyErr?.message || "Unbekannter Fehler.",
    retryable: false,
  };
}

/** Convenience: the string to show the user, request id appended when present. */
export function errorMessage(err: unknown): string {
  const e = toAppError(err);
  return e.requestId ? `${e.message} (Ref: ${e.requestId})` : e.message;
}
