/**
 * Basemap tiles (SPEC §20: CARTO Positron with attribution, graceful fallback to no tiles).
 * Since 2026 CARTO answers keyless requests with a byte-identical "API KEY REQUIRED" watermark
 * tile (HTTP 200), which Leaflet cannot tell from a real tile. The console fetches one probe tile
 * first and treats the watermark, an HTTP error or no network as "tiles unavailable".
 * `VITE_TILE_URL` overrides the template (e.g. a keyed CARTO URL) without a code change.
 */

export const CARTO_POSITRON_URL = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
export const CARTO_WATERMARK_SHA256 = '69be4aecf9f814ba45d585801a5aa41e79b16fc88eafec5b1954a9f06a69e6be'
export const PROBE_ZOOM = 12
export const PROBE_TIMEOUT_MS = 5_000

export type TileProbe = 'ok' | 'watermark' | 'unreachable'
type Fetcher = (input: string, init?: RequestInit) => Promise<Response>

export function tileTemplate(override: string | undefined): string {
  return override && override.trim() !== '' ? override.trim() : CARTO_POSITRON_URL
}

/** Slippy-map tile x/y for a point at zoom z (Web Mercator). */
export function tileXY(lat: number, lng: number, z: number): { x: number; y: number } {
  const n = 2 ** z
  const rad = (lat * Math.PI) / 180
  const x = Math.floor(((lng + 180) / 360) * n)
  const y = Math.floor(((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n)
  return { x, y }
}

export function tileUrl(template: string, z: number, x: number, y: number): string {
  return template.replace('{s}', 'a').replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y)).replace('{r}', '')
}

async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

export async function probeTiles(fetchImpl: Fetcher, template: string, lat: number, lng: number): Promise<TileProbe> {
  const { x, y } = tileXY(lat, lng, PROBE_ZOOM)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)
  try {
    const response = await fetchImpl(tileUrl(template, PROBE_ZOOM, x, y), { signal: controller.signal, mode: 'cors' })
    if (!response.ok) return 'unreachable'
    const digest = await sha256Hex(await response.arrayBuffer())
    return digest === CARTO_WATERMARK_SHA256 ? 'watermark' : 'ok'
  } catch (error) {
    console.warn('[tiles] probe failed', error)
    return 'unreachable'
  } finally {
    clearTimeout(timer)
  }
}
