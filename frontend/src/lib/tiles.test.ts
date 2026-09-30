import { describe, expect, it, vi } from 'vitest'

import { CARTO_POSITRON_URL, CARTO_WATERMARK_SHA256, probeTiles, tileTemplate, tileUrl, tileXY } from './tiles'

async function sha(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

describe('tiles (SPEC §20 CARTO Positron with graceful fallback)', () => {
  it('computes slippy tiles for Mumbai', () => {
    expect(tileXY(19.0, 72.85, 12)).toEqual({ x: 2876, y: 1827 })
  })

  it('fills templates', () => {
    expect(tileUrl(CARTO_POSITRON_URL, 12, 1, 2)).toBe('https://a.basemaps.cartocdn.com/light_all/12/1/2.png')
    expect(tileTemplate(undefined)).toBe(CARTO_POSITRON_URL)
    expect(tileTemplate('  ')).toBe(CARTO_POSITRON_URL)
    expect(tileTemplate(' https://tiles.example/{z}/{x}/{y}.png ')).toBe('https://tiles.example/{z}/{x}/{y}.png')
  })

  it('accepts a real tile', async () => {
    const fetcher = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(async () => new Response(new Uint8Array([1, 2, 3])))
    await expect(probeTiles(fetcher, CARTO_POSITRON_URL, 19, 72.85)).resolves.toBe('ok')
    expect(fetcher).toHaveBeenCalledWith('https://a.basemaps.cartocdn.com/light_all/12/2876/1827.png', expect.objectContaining({ mode: 'cors' }))
  })

  it('recognises the watermark digest', async () => {
    const bytes = new Uint8Array([9, 9, 9])
    expect(CARTO_WATERMARK_SHA256).toHaveLength(64)
    const digest = await sha(bytes)
    const fetcher = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(async () => new Response(bytes))
    const result = await probeTiles(fetcher, CARTO_POSITRON_URL, 19, 72.85)
    expect(result).toBe(digest === CARTO_WATERMARK_SHA256 ? 'watermark' : 'ok')
  })

  it('reports HTTP errors and network failures as unreachable', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    await expect(probeTiles(async () => new Response('x', { status: 503 }), CARTO_POSITRON_URL, 19, 72)).resolves.toBe('unreachable')
    await expect(probeTiles(async () => Promise.reject(new TypeError('offline')), CARTO_POSITRON_URL, 19, 72)).resolves.toBe('unreachable')
  })
})
