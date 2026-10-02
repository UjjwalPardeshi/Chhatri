/**
 * Vite config for the Chhatri console (SPEC §20, §23; binding decision B7).
 * The dev server proxies /api to VITE_API_URL (default http://localhost:8000).
 * `vite --mode mock` loads .env.mock (VITE_MOCK=1) and serves the console on the in-browser mock backend.
 * Tailwind v4 runs through its Vite plugin but only touches CSS that opts in (ADR 0005): the console's
 * plain CSS is passed through unchanged and src/miniapp/miniapp.css is the one Tailwind entry.
 * The `@` alias (src/) exists for the shadcn files in src/miniapp/ui; console code keeps relative imports.
 */
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

const DEFAULT_API_URL = 'http://localhost:8000'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const target = env.VITE_API_URL || DEFAULT_API_URL
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
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
