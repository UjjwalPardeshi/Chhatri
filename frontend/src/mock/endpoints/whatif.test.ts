/** Mock POST /api/whatif/area: verdict parity with the shared vectors, the contract, read-only, and the flag. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { WHATIF_CONDITION_CODES, type WhatIfAlert } from '../../api/opsWhatIf'
import type { MockBackend } from '../backend'
import { MOCK_OFFICER_TOKEN } from '../fixtures'
import { testApi } from '../testkit'
import vectors from '../whatif.vectors.json'
import { whatIfVerdict } from './whatif'

let backend: MockBackend
beforeEach(() => vi.stubEnv('VITE_FEATURES', 'h24_whatif'))
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

async function at(time: string) {
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load('monsoon')
  await kit.api.seek(time)
  return kit.api
}

describe('whatIfVerdict against the shared vectors', () => {
  for (const vector of vectors.vectors) {
    it(`${vector.name}`, () => {
      const verdict = whatIfVerdict({ ...vector.inputs, alert: vector.inputs.alert as WhatIfAlert })
      expect(verdict.fires).toBe(vector.expected.fires)
      expect(verdict.status).toBe(vector.expected.status)
      expect(verdict.conditions).toEqual(vector.expected.conditions)
    })
  }
})

describe('POST /api/whatif/area (mock)', () => {
  it('is 404 while h24_whatif is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const api = await at('17:00')
    await expect(api.whatIfArea({ zone_id: 'Z9' })).rejects.toMatchObject({ code: 'not_found', status: 404 })
  })

  it('with no overrides reproduces what happened: Z7 fires at 17:00, nothing changed', async () => {
    const api = await at('17:00')
    const answer = await api.whatIfArea({ zone_id: 'Z7' })
    expect(answer).toMatchObject({ read_only: true, stored: false, zone_id: 'Z7', at: '2025-08-19T17:00:00+05:30', changed: [] })
    expect(answer.window).toEqual({ start: '2025-08-19T14:00:00+05:30', end: '2025-08-19T17:00:00+05:30' })
    expect(answer.conditions.map((c) => c.code)).toEqual([...WHATIF_CONDITION_CODES])
    expect(answer.baseline.fires).toBe(true)
    expect(answer.scenario).toEqual(answer.baseline)
  })

  it('recomputes: a heat alert does not count, and the verdict follows the conditions', async () => {
    const api = await at('17:00')
    const answer = await api.whatIfArea({ zone_id: 'Z7', overrides: { alert: 'HEATWAVE' } })
    expect(answer.changed).toEqual(['alert'])
    expect(answer.scenario.fires).toBe(false)
    expect(answer.conditions[0]).toMatchObject({ baseline: { met: true }, scenario: { met: false } })
    expect(answer.baseline.fires).toBe(true)
  })

  it('prices the example shop with the engine arithmetic', async () => {
    const api = await at('17:00')
    const answer = await api.whatIfArea({ zone_id: 'Z7', overrides: { hourly_index_pct: [45, 45, 45] }, example_merchant_id: 'S-0142' })
    expect(answer.scenario).toMatchObject({ fires: true, window_index_pct: 45, drop_pct: 55 })
    expect(answer.example).toMatchObject({ merchant_id: 'S-0142', amount_paise: 120_500, amount_label: '₹1,205', formula_en: '½ × ₹4,380 × 55% = ₹1,205' })
  })

  it('is read-only: the audit log, feed and ids do not move', async () => {
    const api = await at('17:00')
    const rt = backend.runtime
    const before = JSON.stringify([rt.audit, rt.feed, rt.decisions, rt.triggers, rt.nextId('X')])
    for (const alert of ['NONE', 'RAIN', 'CIVIC'] as const) await api.whatIfArea({ zone_id: 'Z9', overrides: { alert, hourly_index_pct: [49, 49, 49] }, example_merchant_id: undefined })
    const after = JSON.stringify([rt.audit, rt.feed, rt.decisions, rt.triggers, rt.nextId('X')])
    expect(after.replace('"X-000002"', '"X-000001"')).toBe(before)
  })

  it('validates: unknown key, range, length, a future hour, a merchant outside the zone, an unknown zone', async () => {
    const api = await at('17:00')
    const bad = (body: Parameters<typeof api.whatIfArea>[0]) => expect(api.whatIfArea(body)).rejects.toMatchObject({ code: 'validation_error', status: 422 })
    await bad({ zone_id: 'Z7', overrides: { colour: 'red' } as never })
    await bad({ zone_id: 'Z7', overrides: { hourly_index_pct: [1, 2, 1001] } })
    await bad({ zone_id: 'Z7', overrides: { hourly_index_pct: [1, 2] } })
    await bad({ zone_id: 'Z7', overrides: { shops_in_index: -1 } })
    await bad({ zone_id: 'Z7', at: '2025-08-19T18:00:00+05:30' })
    await bad({ zone_id: 'Z3', example_merchant_id: 'S-0142', overrides: { hourly_index_pct: [40, 40, 40] } })
    await expect(api.whatIfArea({ zone_id: 'Z99' })).rejects.toBeInstanceOf(ApiError)
  })
})
