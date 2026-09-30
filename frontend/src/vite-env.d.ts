/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" runs the console on the in-browser mock backend (binding decision B7). */
  readonly VITE_MOCK?: string
  /** Backend origin for the dev proxy (vite.config.ts only). */
  readonly VITE_API_URL?: string
  /** Optional basemap template overriding CARTO Positron (e.g. a keyed CARTO URL). */
  readonly VITE_TILE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
