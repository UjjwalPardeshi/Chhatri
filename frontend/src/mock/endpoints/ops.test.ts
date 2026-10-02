/** Mock GET /api/ops/summary: the definitions of fs-08 10.2 at the replay clock. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../backend'
import { MOCK_OFFICER_TOKEN } from '../fixtures'
import { testApi } from '../testkit'

let backend: MockBackend
beforeEach(() => vi.stubEnv('VITE_FEATURES', 'h8_ops_strip'))
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
  return kit
}

describe('GET /api/ops/summary (mock)', () => {
  it('is 404 while h8_ops_strip is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = await at('17:00')
    await expect(api.opsSummary()).rejects.toMatchObject({ code: 'not_found' })
  })

  it('has nothing paid and nothing open before the trigger', async () => {
    const { api } = await at('16:00')
    const ops = await api.opsSummary()
    expect(ops).toMatchObject({ day: '2025-08-19', open_cases: 0, overdue_cases: 0, next_due_case: null })
    expect(ops.payouts_today).toMatchObject({ credited_count: 0, credited_paise: 0, pending_count: 0, by_zone: {} })
    expect(ops.claims_today).toEqual({ automatic: 0, human: 0, waiting: 0, automatic_share_pct: null })
    expect(ops.holiday_requests_today).toBeNull()
  })

  it('counts decided-but-not-credited payouts as in flight at 17:02, none at 17:05, and agrees with the KPIs', async () => {
    const { api } = await at('17:02')
    const inFlight = await api.opsSummary()
    expect(inFlight.payouts_today.pending_count).toBeGreaterThan(0)
    expect(inFlight.payouts_today.credited_count).toBe(0)
    expect(inFlight.claims_today.automatic).toBe(inFlight.payouts_today.pending_count)
    expect(inFlight.claims_today.automatic_share_pct).toBe(100)
    await api.seek('17:05')
    const done = await api.opsSummary()
    const state = await api.state()
    expect(done.payouts_today.pending_count).toBe(0)
    expect(done.payouts_today.credited_paise).toBe(state.kpis.total_paid_paise)
    expect(done.payouts_today.credited_count).toBe(state.kpis.shops_paid)
    expect(Object.keys(done.payouts_today.by_zone).length).toBeGreaterThan(0)
  })

  it('lists zones largest first and counts holiday requests only with the lender flag', async () => {
    vi.stubEnv('VITE_FEATURES', 'h8_ops_strip,x4_lender_request')
    const { api } = await at('17:06')
    const ops = await api.opsSummary()
    const paise = Object.values(ops.payouts_today.by_zone).map((z) => z.paise)
    expect(paise).toEqual(paise.toSorted((a, b) => b - a))
    expect(ops.holiday_requests_today).toMatchObject({ GRANTED: expect.any(Number) })
  })

  it('counts open cases by kind, and the kinds add up to the open cases', async () => {
    const { api, backend: b } = await at('17:06')
    const ops = await api.opsSummary()
    expect(ops.open_cases).toBe(b.runtime.cases.filter((c) => c.status === 'OPEN').length)
    expect(Object.values(ops.cases_by_kind).reduce((a, n) => a + n, 0)).toBe(ops.open_cases)
    expect(ops.overdue_cases).toBe(0)
  })
})
