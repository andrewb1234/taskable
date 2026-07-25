import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { E2E_API_KEY, E2E_JWT_SECRET } from "./tests/authFixture";

// package.json declares "type": "module", so __dirname is not defined.
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..");
const E2E_PYTHON =
  process.env.E2E_PYTHON ?? (process.env.CI ? "python" : "./.venv/bin/python");

/**
 * Playwright configuration for the realtime-SSE e2e suite.
 *
 * We boot two processes simultaneously via `webServer` array entries:
 *   1. `uvicorn` — the FastAPI backend pointed at a throwaway SQLite file
 *      under `web/tests/.e2e-taskable.db` so the user's ~/.taskable DB is
 *      never touched.
 *   2. `vite`    — the React dev server (proxies /api/v1/* to uvicorn).
 *
 * Both servers are reused across tests (`reuseExistingServer: true`) so local
 * iteration is fast. CI runs get fresh instances.
 */

const E2E_DB_PATH = path.join(REPO_ROOT, "web", "tests", ".e2e-taskable.db");

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false, // UI tests touch shared state (the API's SQLite)
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      // FastAPI — points at a throwaway DB so the user's real
      // ~/.taskable/taskable.db is never mutated by tests. The seed script
      // fails closed unless this exact test database path is configured.
      command:
        `${E2E_PYTHON} -m scripts.seed_e2e && ` +
        `${E2E_PYTHON} -m uvicorn api.main:app ` +
        `--host 127.0.0.1 --port 8000 --log-level warning`,
      url: "http://127.0.0.1:8000/healthz",
      cwd: REPO_ROOT,
      reuseExistingServer: !process.env.CI,
      stdout: "pipe",
      stderr: "pipe",
      timeout: 30_000,
      env: {
        DATABASE_URL: `sqlite:///${E2E_DB_PATH}`,
        E2E_API_KEY,
        JWT_SECRET: E2E_JWT_SECRET,
        LOCAL_AUTH_ENABLED: "true",
        FRONTEND_URL: "http://127.0.0.1:5173",
        MIGRATION_MODE: "check",
        // Browser specs create an isolated session per test. Keep this test
        // harness from exercising the production auth limiter; the backend
        // suite covers limiter behavior directly.
        AUTH_RATE_LIMIT: "100",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173",
      cwd: __dirname,
      reuseExistingServer: !process.env.CI,
      stdout: "pipe",
      stderr: "pipe",
      timeout: 30_000,
    },
  ],
});
