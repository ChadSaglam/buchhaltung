import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Next 16 allows one dev server per project directory and keeps that lock
  // under distDir, so `make check` (Playwright on :3100) refused to start while
  // `make dev` (:3000) was running. The e2e server sets NEXT_DIST_DIR=.next-e2e
  // and gets its own lock, its own cache, and no fight with the dev server.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  turbopack: {
    root: path.join(__dirname),
  },
  // scripts/dev.sh and the Playwright config both serve the app on 127.0.0.1.
  // Without this, Next 16 blocks its own dev chunks as cross-origin, the client
  // bundle never boots, and anything client-side (AuthGuard's redirect, the ⌘K
  // palette, theme toggle) silently does nothing.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
