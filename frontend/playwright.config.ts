import { defineConfig } from "@playwright/test";

const FRONTEND_URL = "http://127.0.0.1:5173";
const BACKEND_URL = "http://127.0.0.1:8420";
const PYTHON = "..\\backend\\.venv\\Scripts\\python.exe";

/**
 * End-to-end tests run the real stack: FastAPI backend (real
 * data/sqlite/sentinel.db) plus the Vite dev server proxying /api → :8420.
 * Auto-scan is disabled at startup so tests see the persisted, deterministic
 * DB contents instead of racing the discovery indexing pass over the watch dirs.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: FRONTEND_URL,
    headless: true,
  },
  webServer: [
    {
      command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port 8420`,
      cwd: "../backend",
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        ...process.env,
        SENTINEL_AUTO_SCAN_ON_STARTUP: "false",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      cwd: "./",
      url: FRONTEND_URL,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});