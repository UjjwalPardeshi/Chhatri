/** Mock GET /api/pricing: 404 while the flag is off, 422 for a lever outside the route, and never a price (the table is only on the real backend). */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../backend'
import { testApi } from '../testkit'
import { PRICING_ONLY_ON_BACKEND } from './pricing'

let backend: MockBackend
beforeEach(() => vi.stubEnv('VITE_FEATURES', 'h24_whatif'))
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

function setup() {
  const kit = testApi()
  backend = kit.backend
  return kit
}

describe('GET /api/pricing (mock)', () => {
  it('is the usual 404 while h24_whatif is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = setup()
    await expect(api.pricing(null)).rejects.toMatchObject({ status: 404, code: 'not_found', message: 'route not found' })
  })

  it('answers 404 with the flag on, saying the pricing table is only on the real backend, whatever the levers', async () => {
    const { api } = setup()
    await expect(api.pricing(null)).rejects.toMatchObject({ status: 404, code: 'not_found', message: PRICING_ONLY_ON_BACKEND })
    await expect(api.pricing({ floor_pct: 55, share_pct: 60, cap_rupees: 3000, loading_pct: 30 })).rejects.toMatchObject({ status: 404, message: PRICING_ONLY_ON_BACKEND })
  })

  it('checks the levers like the real route first: 422 for one outside its bounds', async () => {
    const { api } = setup()
    await expect(api.client.get('/api/pricing?share=5')).rejects.toMatchObject({ status: 422, code: 'validation_error', fields: { share: 'a whole number from 10 to 100' } })
    await expect(api.client.get('/api/pricing?cap=2500.5')).rejects.toMatchObject({ status: 422, fields: { cap: 'a whole number from 500 to 10000' } })
    await expect(api.client.get('/api/pricing?loading=61')).rejects.toMatchObject({ status: 422, fields: { loading: 'a whole number from 0 to 60' } })
  })
})
