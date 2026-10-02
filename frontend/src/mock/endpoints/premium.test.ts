/** Mock POST /api/premium/link and POST /api/webhooks/paytm: the buy flow of DEMO.md (Ramesh, Z3, ₹14.16 a day, ₹424.80). */
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { afterEach, describe, expect, it } from 'vitest'

import type { MockBackend } from '../backend'
import { createMockFetch } from '../fetch'
import { MOCK_OFFICER_TOKEN, zonePremiumPaise } from '../fixtures'
import premiums from '../data/premiums.json'
import { testApi } from '../testkit'
import { simulatedLinkCode } from './premium'

let backend: MockBackend
afterEach(() => backend?.dispose())

async function buyCoverSession(at = '18:00') {
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load('buy_cover')
  if (at !== '18:00') await kit.api.seek(at)
  return kit
}

const BACKEND_PRICES = resolve(__dirname, '../../../../backend/artifacts/premiums.json')

describe('zone prices', () => {
  it('copies the backend artefact, so a mock quote reads the real zone price', () => {
    expect(zonePremiumPaise('Z7')).toBe(1862)
    expect(zonePremiumPaise('Z3')).toBe(1416)
    expect(zonePremiumPaise('Z99')).toBe(200)
  })

  it.runIf(existsSync(BACKEND_PRICES))('equals backend/artifacts/premiums.json', () => {
    expect(premiums).toEqual(JSON.parse(readFileSync(BACKEND_PRICES, 'utf8')))
  })
})

describe('simulated link code', () => {
  it('is the backend hash of merchant, amount, purpose and sequence', () => {
    const purpose = 'Chhatri cover premium, 30 days from 2025-08-25'
    expect(simulatedLinkCode('S-0907', 42_480, purpose, 1)).toBe('7BFFBE')
    expect(simulatedLinkCode('S-0907', 42_480, purpose, 2)).toBe('1BC6AA')
  })
})

describe('POST /api/premium/link', () => {
  it('quotes Ramesh 30 days of Z3 premium, BLOCKED behind the alert, with a simulated link', async () => {
    const { api } = await buyCoverSession()
    const { quote, premium } = await api.premiumLink('S-0907')
    expect(quote).toEqual({
      id: 'Q-000001',
      merchant_id: 'S-0907',
      outcome: 'BLOCKED',
      requested_at: '2025-08-18T18:00:00+05:30',
      starts_on: '2025-08-25',
      premium_per_day_paise: 1416,
      premium_per_day_label: '₹14.16',
      first_payment_paise: 42_480,
      first_payment_label: '₹424.80',
      days_prepaid: 30,
      reason_en: 'New cover starts after the waiting period',
      reason_hi: 'नया कवर वेटिंग पीरियड के बाद शुरू होता है',
      blocking_alert_id: 'A-20250818-01',
    })
    expect(premium).toEqual({
      id: 'PR-000001',
      merchant_id: 'S-0907',
      amount_paise: 42_480,
      amount_label: '₹424.80',
      method: 'PAYMENT_LINK',
      covers_from: '2025-08-25',
      covers_to: '2025-09-23',
      status: 'PENDING',
      link_id: 'sim-7BFFBE',
      link_url: 'https://paytm.me/sim-7BFFBE',
      source: 'simulated',
      created_at: '2025-08-18T18:00:00+05:30',
      paid_at: null,
    })
  })

  it('quotes OK when no alert is near, and numbers the next quote and link', async () => {
    const { api } = await buyCoverSession()
    await api.premiumLink('S-0907')
    await api.load('illness')
    const quiet = await api.premiumLink('S-0907')
    expect(quiet.quote).toMatchObject({ id: 'Q-000001', outcome: 'OK', starts_on: '2025-08-28', blocking_alert_id: null })
    expect(quiet.quote.reason_en).toBe('No alert for your area. New cover starts after the 7-day waiting period')
    await api.load('buy_cover')
    await api.premiumLink('S-0907')
    expect((await api.premiumLink('S-0907')).premium).toMatchObject({ id: 'PR-000002', link_id: 'sim-1BC6AA' })
  })

  it('answers the chat quote and the API quote with the same first link', async () => {
    const { api, backend: b } = await buyCoverSession()
    await api.sendText('S-0907', 'Red alert tomorrow. Cover me today.')
    expect(b.runtime.premiums.map((p) => p.link_url)).toEqual(['https://paytm.me/sim-7BFFBE'])
  })

  it('needs the officer token and a well-formed known merchant', async () => {
    const { backend: b } = await buyCoverSession()
    const fetcher = createMockFetch(b)
    const post = (headers: Record<string, string>, body: unknown) =>
      fetcher('/api/premium/link', { method: 'POST', headers, body: JSON.stringify(body) })
    const anonymous = await post({}, { merchant_id: 'S-0907' })
    expect(anonymous.status).toBe(401)
    expect(await anonymous.json()).toMatchObject({ ok: false, error: { code: 'unauthorized', message: 'officer token required' } })
    const wrong = await post({ Authorization: 'Bearer nope' }, { merchant_id: 'S-0907' })
    expect(wrong.status).toBe(403)
    expect(await wrong.json()).toMatchObject({ error: { code: 'forbidden', message: 'invalid officer token' } })
    const auth = { Authorization: `Bearer ${MOCK_OFFICER_TOKEN}` }
    const missing = await post(auth, {})
    expect(missing.status).toBe(422)
    expect(await missing.json()).toMatchObject({ error: { code: 'validation_error', message: 'invalid request', fields: { merchant_id: expect.any(String) } } })
    const unknown = await post(auth, { merchant_id: 'S-9999' })
    expect(unknown.status).toBe(404)
    expect(await unknown.json()).toMatchObject({ error: { code: 'not_found', message: 'merchant S-9999 not found' } })
  })
})

describe('POST /api/webhooks/paytm', () => {
  it('marks the premium paid and makes a cover that starts on 25 August', async () => {
    const { api, backend: b } = await buyCoverSession()
    const { premium } = await api.premiumLink('S-0907')
    expect(await api.paytmWebhook(premium?.link_id ?? '')).toEqual({ status: 'paid', link_id: 'sim-7BFFBE' })
    expect(b.runtime.premiums[0]).toMatchObject({ status: 'PAID', paid_at: '2025-08-18T18:00:00+05:30' })
    expect(await api.cover('S-0907')).toMatchObject({ cover_id: 'CV-S-0907-20250825', status: 'WAITING', starts_on: '2025-08-25', prepaid_through: '2025-09-23' })
    const told = b.runtime.messages.filter((m) => m.merchant_id === 'S-0907').at(-1)
    expect(told?.text_en).toBe('Ramesh ji, we received your ₹424.80 premium. Your cover starts on 25 August and is paid through 23 September.')
    expect(told?.text_hi).toBe('रमेश जी, आपका ₹424.80 का प्रीमियम मिल गया। आपका कवर 25 अगस्त से शुरू होगा और 23 सितंबर तक का प्रीमियम जमा है।')
    expect(b.runtime.feed.at(-1)?.text_en).toBe('Ramesh Vada Pav paid ₹424.80 premium · covered 25 Aug–23 Sep')
  })

  it('answers a repeated callback with duplicate and changes nothing', async () => {
    const { api, backend: b } = await buyCoverSession()
    await api.premiumLink('S-0907')
    await api.paytmWebhook('sim-7BFFBE')
    const sent = b.runtime.messages.length
    expect(await api.paytmWebhook('sim-7BFFBE')).toEqual({ status: 'duplicate', link_id: 'sim-7BFFBE' })
    expect(b.runtime.messages).toHaveLength(sent)
  })

  it('ignores a failed payment and rejects an unknown link', async () => {
    const { api, backend: b } = await buyCoverSession()
    await api.premiumLink('S-0907')
    const fetcher = createMockFetch(b)
    const failed = await fetcher('/api/webhooks/paytm', { method: 'POST', body: JSON.stringify({ link_id: 'sim-7BFFBE', status: 'TXN_FAILURE', txn_id: 'T-1' }) })
    expect(await failed.json()).toEqual({ ok: true, data: { status: 'ignored', link_id: 'sim-7BFFBE' } })
    expect(b.runtime.premiums[0].status).toBe('PENDING')
    await expect(api.paytmWebhook('sim-ZZZZZZ')).rejects.toMatchObject({ code: 'not_found', status: 404, message: 'payment link sim-ZZZZZZ not found' })
    const bad = await fetcher('/api/webhooks/paytm', { method: 'POST', body: JSON.stringify({ status: 'TXN_SUCCESS' }) })
    expect(bad.status).toBe(422)
  })

  it('extends the prepaid date of an existing cover, contiguously', async () => {
    const { api, backend: b } = await buyCoverSession()
    await api.load('monsoon')
    const first = await api.premiumLink('S-0142')
    await api.paytmWebhook(first.premium?.link_id ?? '')
    expect(b.runtime.premiums[0]).toMatchObject({ covers_from: '2025-08-23', covers_to: '2025-09-21', status: 'PAID' })
    expect(await api.cover('S-0142')).toMatchObject({ cover_id: 'CV-0142', prepaid_through: '2025-09-21' })
  })
})
