/** The query and the strict parser of GET /api/pricing: the real answer passes, and a figure the page cannot trust is a contract violation. */
import { describe, expect, it, vi } from 'vitest'

import { PRICING_DATA } from '../test/pricingFixture'
import { ApiClient, type FetchLike } from './client'
import { createApi } from './endpoints'
import { parsePricing, pricingPath } from './pricing'

type Body = typeof PRICING_DATA
type Zone = Body['zones'][number]

const VIOLATION = expect.objectContaining({ code: 'contract_violation' })
const PUBLISHED = { floor_pct: 50, share_pct: 50, cap_rupees: 2500, loading_pct: 35 }

const withZone = (index: number, over: Partial<Record<keyof Zone, unknown>>) => ({ ...PRICING_DATA, zones: PRICING_DATA.zones.map((zone, i) => (i === index ? { ...zone, ...over } : zone)) })
const withCity = (over: Partial<Record<keyof Body['city'], unknown>>) => ({ ...PRICING_DATA, city: { ...PRICING_DATA.city, ...over } })

describe('parsePricing', () => {
  it('accepts the real answer at the published rules and returns it unchanged', () => {
    expect(parsePricing(PRICING_DATA)).toEqual(PRICING_DATA)
  })

  it("accepts a zone not priced today, a city with no real drop and no payout, and ignores keys it does not know", () => {
    const body = {
      ...withZone(2, { current_premium_per_day_paise: null, loss_ratio_at_current_price: null }),
      city: { ...PRICING_DATA.city, real_drops: 0, real_drops_paid: 0, recall: null, payouts: 0, payouts_no_real_drop: 0, false_payout_share: null },
      extra: 'ignored',
    }
    const parsed = parsePricing(body)
    expect(parsed.zones[2]).toMatchObject({ zone_id: 'Z21', current_premium_per_day_paise: null, loss_ratio_at_current_price: null })
    expect(parsed.city).toMatchObject({ recall: null, false_payout_share: null })
    expect(parsed).not.toHaveProperty('extra')
  })

  it.each([
    ['money in fractions of a paisa', withZone(0, { premium_per_day_paise: 18.62 })],
    ['a negative count of shops', withZone(0, { shops: -1 })],
    ["a loss ratio with no premium today", withZone(0, { current_premium_per_day_paise: null })],
    ['a zone id that is not a zone', withZone(0, { zone_id: 'Parel' })],
    ['a zone listed twice', withZone(1, { zone_id: 'Z7' })],
    ['a zone with no name', withZone(0, { name: '' })],
    ['no zones', { ...PRICING_DATA, zones: [] }],
    ["a lowest premium that is not the zones' own", withCity({ premium_min_paise: 600 })],
    ['a median above the highest premium', withCity({ premium_median_paise: 4000 })],
    ['more real drops paid than real drops', withCity({ real_drops_paid: 149 })],
    ['a recall with no real drop', withCity({ real_drops: 0, real_drops_paid: 0 })],
    ['no recall with real drops', withCity({ recall: null })],
    ['a recall that contradicts its counts', withCity({ recall: 0.9 })],
    ['a false payout share that contradicts its counts', withCity({ false_payout_share: 0.5 })],
    ['a lever outside the route', { ...PRICING_DATA, levers: { ...PUBLISHED, share_pct: 5 } }],
    ["a floor priced that is not one of the table's", { ...PRICING_DATA, levers: { ...PUBLISHED, floor_pct: 47 } }],
    ["a published floor that is not one of the table's", { ...PRICING_DATA, rules: { ...PRICING_DATA.rules, floor_pct: 47 } }],
    ['rules with no version', { ...PRICING_DATA, rules: { ...PUBLISHED, min_per_day_rupees: 2 } }],
    ['floors out of order', { ...PRICING_DATA, floors: [40, 50, 45, 55, 60] }],
    ['no city', { ...PRICING_DATA, city: null }],
    ['a list instead of the answer', [PRICING_DATA]],
  ])('rejects %s', (_name, body) => {
    expect(() => parsePricing(body)).toThrowError(VIOLATION)
    expect(() => parsePricing(body)).toThrowError(/^pricing/)
  })
})

describe('pricingPath', () => {
  it('asks for the published rules with no query, and sends every lever otherwise', () => {
    expect(pricingPath(null)).toBe('/api/pricing')
    expect(pricingPath({ floor_pct: 55, share_pct: 60, cap_rupees: 3000, loading_pct: 30 })).toBe('/api/pricing?floor=55&share=60&cap=3000&loading=30')
  })

  it('refuses a lever outside the route before it reaches the server', () => {
    expect(() => pricingPath({ ...PUBLISHED, share_pct: 5 })).toThrowError(expect.objectContaining({ code: 'VALIDATION_ERROR', fields: { share: 'a whole number from 10 to 100' } }))
    expect(() => pricingPath({ ...PUBLISHED, cap_rupees: 2500.5 })).toThrowError(expect.objectContaining({ fields: { cap: 'a whole number from 500 to 10000' } }))
  })
})

describe('api.pricing', () => {
  it('gets the levers it is given, with the signal, and parses the answer', async () => {
    const fetcher = vi.fn<FetchLike>(() => Promise.resolve(new Response(JSON.stringify({ ok: true, data: PRICING_DATA }), { status: 200 })))
    const api = createApi(new ApiClient(fetcher))
    const answer = await api.pricing({ ...PUBLISHED, share_pct: 60 }, new AbortController().signal)
    expect(fetcher.mock.calls[0][0]).toBe('/api/pricing?floor=50&share=60&cap=2500&loading=35')
    expect(answer.zones.map((zone) => zone.zone_id)).toEqual(['Z7', 'Z8', 'Z21'])
    await api.pricing(null)
    expect(fetcher.mock.calls[1][0]).toBe('/api/pricing')
  })

  it('rejects a broken body as a contract violation', async () => {
    const api = createApi(new ApiClient(() => Promise.resolve(new Response(JSON.stringify({ ok: true, data: { label: 'x' } }), { status: 200 }))))
    await expect(api.pricing(null)).rejects.toMatchObject({ code: 'contract_violation' })
  })
})
