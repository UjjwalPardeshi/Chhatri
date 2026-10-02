/** Unit/component test config (SPEC §22: vitest for formatters, colour scale and UI). */
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'happy-dom',
    // Lazy pages and the geo JSON need ~2 s per test on an idle machine and 10-15 s when the CPU is shared
    // (a full parallel run on a busy laptop or runner). The limit is a safety net, not a performance gate;
    // setup.ts keeps the Testing Library wait below it so a missing element fails with its DOM dump.
    testTimeout: 30_000,
    // Every feature flag starts off, whatever the shell or frontend/.env.local hold for `make dev`; a test turns
    // one on with vi.stubEnv (the backend's test settings pin CHHATRI_FEATURES the same way).
    env: { VITE_FEATURES: '' },
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'text'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts', 'src/mock/data/**'],
      thresholds: { lines: 90, statements: 90, functions: 85, branches: 80 },
    },
  },
})
