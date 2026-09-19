import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Next 16 allows one dev server per project directory and keeps that lock
  // under distDir, so `make check` (Playwright on :3100) refused to start while
  // `make dev` (:3000) was running. The e2e server sets NEXT_DIST_DIR=.next-e2e
  // and gets its own lock, its own cache, and no fight with the dev server.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // B-80: the image copies `.next/standalone` — a server plus only the modules
  // the trace actually reached — instead of the source tree and every
  // devDependency `npm ci` installed. `next start` is not in that bundle; the
  // runtime stage runs `node server.js`, which is what standalone emits.
  output: "standalone",
  turbopack: {
    root: path.join(__dirname),
  },
  // scripts/dev.sh and the Playwright config both serve the app on 127.0.0.1.
  // Without this, Next 16 blocks its own dev chunks as cross-origin, the client
  // bundle never boots, and anything client-side (AuthGuard's redirect, the ⌘K
  // palette, theme toggle) silently does nothing.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Step 3 of docs/IA-2026-09-14.md: the pages moved under the surface they
  // belong to, so their old addresses have to keep working. Temporary (307),
  // not permanent — a 308 is cached by the browser forever and would outlive
  // the release these redirects are meant to cover.
  // B-108: the frontend's own headers. The API sets its four separately
  // (`core/security_headers.py`) — two servers, two responses, and a browser
  // reads whichever one it is talking to.
  //
  // The CSP here is looser than the API's on purpose: Next ships inline
  // bootstrap scripts and (in development) eval'd HMR chunks, so `script-src`
  // has to allow them or the app does not boot. What matters for the risk this
  // was opened for — a token in localStorage — is `frame-ancestors` and
  // `base-uri`, which are absolute either way. Tightening `script-src` with a
  // nonce is worth doing and is not a header change; it is a rendering change.
  async headers() {
    const csp = [
      "default-src 'self'",
      // 'unsafe-eval' only in development: Turbopack's HMR needs it, the
      // standalone build does not.
      `script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      // The API is a different origin (:8000), so it has to be named.
      `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000 http://127.0.0.1:8000"}`,
      "object-src 'none'",
      "frame-ancestors 'none'",
      "base-uri 'none'",
      "form-action 'self'",
    ].join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
  async redirects() {
    return [
      { source: "/dashboard/rechnungen", destination: "/dashboard/belege", permanent: false },
      { source: "/dashboard/rechnungen/:path*", destination: "/dashboard/belege/:path*", permanent: false },
      { source: "/dashboard/scanner", destination: "/dashboard/belege/scanner", permanent: false },
      { source: "/dashboard/scanner/:path*", destination: "/dashboard/belege/scanner/:path*", permanent: false },
      { source: "/dashboard/kontoauszug", destination: "/dashboard/bank", permanent: false },
      { source: "/dashboard/kontoauszug/:path*", destination: "/dashboard/bank/:path*", permanent: false },
      { source: "/dashboard/abgleich", destination: "/dashboard/bank/abgleich", permanent: false },
      { source: "/dashboard/abgleich/:path*", destination: "/dashboard/bank/abgleich/:path*", permanent: false },
      { source: "/dashboard/insights", destination: "/dashboard/bank/buchungen", permanent: false },
      { source: "/dashboard/insights/:path*", destination: "/dashboard/bank/buchungen/:path*", permanent: false },
    ];
  },
};

export default nextConfig;
