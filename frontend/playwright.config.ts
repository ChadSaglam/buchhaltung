import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    // In CI, run against the production server (the workflow builds first).
    // The dev server's HMR runtime is unreliable in the CI sandbox and can
    // prevent client effects (e.g. the AuthGuard redirect) from committing,
    // so a prod build gives a faithful, deterministic run. Locally we keep
    // the dev server for fast iteration.
    command: process.env.CI ? "npm run start -- -p 3000" : "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
