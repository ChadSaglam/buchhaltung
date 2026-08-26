import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
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
