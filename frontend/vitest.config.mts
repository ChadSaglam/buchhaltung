import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Unit tests for pure helpers (B-11) plus the small shared state components
// (B-18: EmptyState / ErrorState / PageSkeleton). Pages stay covered by
// Playwright (e2e/). Component tests opt into jsdom with a
// `// @vitest-environment jsdom` docblock; helpers run in plain node.
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    environment: "node",
  },
});
