import os from "node:os";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// The SPA is served by Vite on E2E_PORT and proxies /api to a legacy Uvicorn
// server on API_PORT with an isolated SQLite database. This keeps the fast E2E
// path independent of the Worker runtime while exercising the real frontend.
const E2E_PORT = 8010;
const API_PORT = 8787;
const E2E_BASE_URL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${E2E_PORT}`;
const E2E_DB = process.env.E2E_DB ?? path.join(os.tmpdir(), "octopod-e2e.db");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: E2E_BASE_URL,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : [
        {
          command: [
            "cd ../backend &&",
            `rm -f ${JSON.stringify(E2E_DB)} &&`,
            `DATABASE_URL=${JSON.stringify(`sqlite:///${E2E_DB}`)}`,
            "SEED_DEMO=true",
            "AUTO_CREATE_TABLES=true",
            "SECRET_KEY=test-secret",
            "uv run uvicorn app.main:app --app-dir src",
            `--host 127.0.0.1 --port ${API_PORT}`,
          ].join(" "),
          url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
          // Always start a fresh server so tests never write to a developer's
          // local database or reuse a stale process.
          reuseExistingServer: false,
          timeout: 60_000,
        },
        {
          command: `npm run dev -- --host 127.0.0.1 --port ${E2E_PORT}`,
          url: E2E_BASE_URL,
          reuseExistingServer: false,
          timeout: 60_000,
        },
      ],
});
