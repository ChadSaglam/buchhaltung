import { afterEach, describe, expect, it, vi } from "vitest";

import { errorMessage, toAppError } from "./errors";

function axiosLike(status: number, data?: unknown, headers?: Record<string, string>) {
  return { response: { status, data, headers } };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("toAppError", () => {
  it("prefers the backend error envelope over the status text", () => {
    const err = axiosLike(404, {
      error: { code: "booking_not_found", message: "Buchung existiert nicht.", request_id: "req-1" },
    });
    expect(toAppError(err)).toEqual({
      code: "booking_not_found",
      message: "Buchung existiert nicht.",
      status: 404,
      requestId: "req-1",
      fields: undefined,
      retryable: false,
    });
  });

  it("falls back to the German status message when the body is not an envelope", () => {
    const e = toAppError(axiosLike(403, "<html>forbidden</html>"));
    expect(e.code).toBe("http_403");
    expect(e.message).toBe("Dafür fehlt dir die Berechtigung.");
    expect(e.retryable).toBe(false);
  });

  it("uses a generic message for a status without a translation", () => {
    expect(toAppError(axiosLike(418)).message).toBe("Die Anfrage ist fehlgeschlagen.");
  });

  it("accepts FastAPI's plain {detail} shape", () => {
    const e = toAppError(axiosLike(400, { detail: "Datei zu klein." }));
    expect(e.message).toBe("Datei zu klein.");
    expect(e.code).toBe("http_400");
  });

  it("carries 422 field errors through", () => {
    const fields = [{ field: "betrag", message: "muss eine Zahl sein" }];
    const e = toAppError(axiosLike(422, { error: { code: "validation_error", message: "Ungültig", fields } }));
    expect(e.fields).toEqual(fields);
  });

  it("reads the request id from the response header when the body has none", () => {
    const e = toAppError(axiosLike(500, undefined, { "x-request-id": "hdr-7" }));
    expect(e.requestId).toBe("hdr-7");
  });

  it.each([408, 429, 500, 502, 503, 504])("marks %i as retryable", (status) => {
    expect(toAppError(axiosLike(status)).retryable).toBe(true);
  });

  it.each([400, 401, 404, 409, 422])("marks %i as not retryable", (status) => {
    expect(toAppError(axiosLike(status)).retryable).toBe(false);
  });

  it("maps a timeout (axios ECONNABORTED or a 'timeout' message)", () => {
    expect(toAppError({ code: "ECONNABORTED" }).code).toBe("timeout");
    expect(toAppError({ message: "timeout of 5000ms exceeded" }).code).toBe("timeout");
  });

  it("maps a network failure to a hint about the backend", () => {
    const e = toAppError({ code: "ERR_NETWORK" });
    expect(e).toMatchObject({ code: "network", retryable: true });
    expect(e.message).toMatch(/Backend/);
  });

  it("treats an aborted request as benign", () => {
    const e = toAppError(new DOMException("cancelled", "AbortError"));
    expect(e).toEqual({ code: "aborted", message: "Abgebrochen.", retryable: true });
  });

  it("reports offline before looking at the response", () => {
    vi.stubGlobal("navigator", { onLine: false });
    const e = toAppError(axiosLike(500));
    expect(e.code).toBe("offline");
    expect(e.retryable).toBe(true);
  });

  it("falls back to the raw message, then to 'Unbekannter Fehler.'", () => {
    expect(toAppError(new Error("boom"))).toEqual({ code: "unknown", message: "boom", retryable: false });
    expect(toAppError(undefined).message).toBe("Unbekannter Fehler.");
    expect(toAppError("string").message).toBe("Unbekannter Fehler.");
  });
});

describe("errorMessage", () => {
  it("appends the request id when present", () => {
    const err = axiosLike(500, { error: { code: "x", message: "Kaputt.", request_id: "abc" } });
    expect(errorMessage(err)).toBe("Kaputt. (Ref: abc)");
  });

  it("returns the bare message otherwise", () => {
    expect(errorMessage({ code: "ERR_NETWORK" })).toBe("Server nicht erreichbar. Läuft das Backend?");
  });
});
