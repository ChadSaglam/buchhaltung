import { existsSync } from "node:fs";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// Dedicated port: port 3000 is often taken by another Next.js dev server on a
// developer machine, and `reuseExistingServer` would then test the wrong app
// (the symptom is a Next 404 on /login).
const E2E_PORT = process.env.E2E_PORT ?? "3100";
// The e2e backend: a throw-away SQLite database created from the models
// (AUTO_CREATE_TABLES), so no Postgres or Alembic is needed to run the
// happy path. Removed on every start for a clean slate.
const API_PORT = process.env.E2E_API_PORT ?? "8100";
const API_URL = `http://127.0.0.1:${API_PORT}`;
const BACKEND_DIR = path.join(__dirname, "..", "backend");
// `make setup` puts the backend toolchain in backend/venv; CI installs it globally.
const PYTHON = existsSync(path.join(BACKEND_DIR, "venv", "bin", "python")) ? "venv/bin/python" : "python3";

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
  webServer: [
    {
      command: `rm -rf e2e.db e2e-data && ${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --log-level warning`,
      cwd: BACKEND_DIR,
      url: `${API_URL}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      // Keep `make check` readable: the API's request log is noise here, but
      // anything it writes to stderr (tracebacks, startup failures) must
      // still reach the terminal.
      stdout: "ignore",
      stderr: "pipe",
      env: {
        DATABASE_URL: "sqlite+aiosqlite:///./e2e.db",
        AUTO_CREATE_TABLES: "1",
        // Receipt uploads (B-09) land in a throw-away directory next to the DB.
        STORAGE_LOCAL_DIR: "./e2e-data",
        ENVIRONMENT: "test",
        SECRET_KEY: "e2e-only-secret-not-used-outside-playwright",
        CORS_ORIGINS: `http://127.0.0.1:${E2E_PORT},http://localhost:${E2E_PORT}`,
        SENTRY_DSN: "",
      },
    },
    {
      // In CI, run against the production server (the workflow builds first).
      // The dev server's HMR runtime is unreliable in the CI sandbox and can
      // prevent client effects (e.g. the AuthGuard redirect) from committing,
      // so a prod build gives a faithful, deterministic run. Locally we keep
      // the dev server for fast iteration.
      command: process.env.CI ? `npm run start -- -p ${E2E_PORT}` : `npm run dev -- -p ${E2E_PORT}`,
      url: `http://127.0.0.1:${E2E_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      // NEXT_PUBLIC_* is inlined at build time: the CI build step must export
      // the same value (see .github/workflows/ci.yml).
      env: { NEXT_PUBLIC_API_URL: API_URL },
    },
  ],
});
