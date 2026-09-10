import { defineConfig, devices } from "@playwright/test";

// Dedicated port: port 3000 is often taken by another Next.js dev server on a
// developer machine, and `reuseExistingServer` would then test the wrong app
// (the symptom is a Next 404 on /login).
const E2E_PORT = process.env.E2E_PORT ?? "3100";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  // Local runs hit a cold `next dev` compile on the first request, which
  // routinely exceeds Playwright's 5 s default and reports a false failure.
  expect: { timeout: process.env.CI ? 10_000 : 20_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? `http://127.0.0.1:${E2E_PORT}`,
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
    command: process.env.CI ? `npm run start -- -p ${E2E_PORT}` : `npm run dev -- -p ${E2E_PORT}`,
    url: `http://127.0.0.1:${E2E_PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
