/**
 * Vite config for the Chhatri console (SPEC §20, §23; binding decision B7).
 * The dev server proxies /api to VITE_API_URL (default http://localhost:8000).
 * `vite --mode mock` loads .env.mock (VITE_MOCK=1) and serves the console on the in-browser mock backend.
 */
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const DEFAULT_API_URL = 'http://localhost:8000'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const target = env.VITE_API_URL || DEFAULT_API_URL
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target, changeOrigin: true },
      },
    },
    build: {
      chunkSizeWarningLimit: 700,
    },
  }
})
