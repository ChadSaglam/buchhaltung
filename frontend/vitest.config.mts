import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Unit tests for pure helpers only (B-11). Components and pages stay covered
// by Playwright (e2e/), so no DOM environment or React plugin is wired here.
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
