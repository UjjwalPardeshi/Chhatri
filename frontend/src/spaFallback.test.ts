/** The static build's deep-link fallback (card 7.1): a copy of index.html named 404.html, so a static host that answers an unknown path with its 404 page still opens the app. */
import { describe, expect, it, vi } from 'vitest'

import { spaFallback } from '../vite.spa-fallback.ts'

type Hook = { handler: (this: unknown, ...args: unknown[]) => void }

function run(bundle: Record<string, unknown>) {
  const emitFile = vi.fn<(file: object) => void>()
  const plugin = spaFallback()
  ;(plugin.generateBundle as unknown as Hook).handler.call({ emitFile }, {}, bundle)
  return emitFile
}

describe('spaFallback', () => {
  it('emits 404.html with the same source as index.html, after the html plugin has run', () => {
    const plugin = spaFallback()
    expect(plugin.enforce).toBe('post')
    expect((plugin.generateBundle as unknown as { order: string }).order).toBe('post')
    const emitFile = run({ 'index.html': { type: 'asset', fileName: 'index.html', source: '<!doctype html><div id="root"></div>' } })
    expect(emitFile).toHaveBeenCalledWith({ type: 'asset', fileName: '404.html', source: '<!doctype html><div id="root"></div>' })
  })

  it('fails the build when there is no index.html to copy, rather than shipping a host that 404s deep links', () => {
    expect(() => run({ 'assets/app.js': { type: 'chunk' } })).toThrow(/index\.html/)
  })
})
