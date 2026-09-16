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
