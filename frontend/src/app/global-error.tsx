"use client";

import { useEffect } from "react";

/**
 * Last-resort boundary: catches errors thrown in the root layout itself, where
 * `error.tsx` cannot render. Must ship its own <html>/<body>.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[global error]", error);
  }, [error]);

  return (
    <html lang="de">
      <body
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
          background: "#f6f8fb",
          color: "#0b1220",
          margin: 0,
          padding: "1.5rem",
        }}
      >
        <div style={{ maxWidth: 420, textAlign: "center" }}>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 600, margin: 0 }}>
            Die App konnte nicht gestartet werden
          </h1>
          <p style={{ marginTop: 8, fontSize: "0.875rem", opacity: 0.7 }}>
            Bitte lade die Seite neu. Bleibt der Fehler bestehen, melde dich beim Support
            {error.digest ? ` mit der Referenz ${error.digest}` : ""}.
          </p>
          <button
            onClick={reset}
            style={{
              marginTop: 20,
              padding: "0.55rem 1.1rem",
              borderRadius: 10,
              border: "1px solid #d5dbe6",
              background: "#fff",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Neu laden
          </button>
        </div>
      </body>
    </html>
  );
}
