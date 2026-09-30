/** Mock entry point (B7): loads geo lazily and serves the envelope API. */
import { describe, expect, it } from 'vitest'

import { startMock } from './index'

describe('startMock', () => {
  it('starts a backend with the ward geometry and a fetch that speaks the envelope', async () => {
    const env = await startMock()
    const response = await env.fetch('/api/session', {})
    expect(await response.json()).toEqual({ ok: true, data: { officer_token: 'mock-officer-token' } })
    expect(env.backend.geo.zones.features).toHaveLength(24)
    env.backend.dispose()
  })
})
