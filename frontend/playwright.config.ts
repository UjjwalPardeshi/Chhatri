/**
 * Playwright E2E (SPEC §22, binding decision B7): chromium only.
 * - project "mock": starts the console in mock mode on E2E_PORT (default 4273) and runs the smoke suite.
 * - project "live": runs the same suite against a running backend + console at CONSOLE_URL.
 */
import { defineConfig, devices } from '@playwright/test'

const E2E_PORT = Number(process.env.E2E_PORT ?? '4273')
const LIVE_URL = process.env.CONSOLE_URL
const MOCK_URL = `http://127.0.0.1:${E2E_PORT}`

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],
  use: {
    viewport: { width: 1280, height: 720 },
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'mock', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 720 }, baseURL: MOCK_URL } },
    { name: 'live', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 720 }, baseURL: LIVE_URL } },
  ],
  webServer: LIVE_URL
    ? undefined
    : {
        command: `npx vite --mode mock --host 127.0.0.1 --port ${E2E_PORT} --strictPort`,
        url: MOCK_URL,
        reuseExistingServer: false,
        timeout: 60_000,
      },
})
