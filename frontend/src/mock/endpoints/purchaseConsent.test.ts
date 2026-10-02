/**
 * Mock parity of the consent block of a cover purchase (N6, fs-07 sections 9.3 and 9.5; backend consent/purchase.py
 * and consent/ledger.py): with n6_consents on, a merchant with no live cover must send the two purposes needed to buy
 * and the notice in force, or the link is refused with 422 and nothing is stored. The ticks become consent only when
 * the link is paid: PAYMENT_APP at the link request time, and a link bought from the chat grants sales and settlement
 * as PAYMENT_CHAT.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../backend'
import { MOCK_OFFICER_TOKEN } from '../fixtures'
import { testApi } from '../testkit'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

const REQUIRED = ['SALES_DATA_FOR_CLAIM', 'SETTLEMENT_DEDUCTION'] as const

async function ramesh(features = 'n6_consents') {
  vi.stubEnv('VITE_FEATURES', features)
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load('buy_cover')
  return kit
}

const granted = (b: MockBackend) => b.runtime.audit.filter((e) => e.action === 'consent.granted')

describe('POST /api/premium/link with n6_consents on', () => {
  it('refuses a merchant with no cover who sends no consents, with 422 and the fields, and stores nothing', async () => {
    const { api } = await ramesh()
    await expect(api.premiumLink('S-0907')).rejects.toMatchObject({ status: 422, fields: { consents: 'required purposes missing', notice_version: 'out of date' } })
    expect(backend.runtime.premiums).toEqual([])
    expect(backend.runtime.quotes).toEqual([])
  })

  it('refuses one required purpose alone, and an old notice', async () => {
    const { api } = await ramesh()
    await expect(api.premiumLink('S-0907', { consents: ['SALES_DATA_FOR_CLAIM'], notice_version: 'notice-1' })).rejects.toMatchObject({ status: 422, fields: { consents: 'required purposes missing' } })
    await expect(api.premiumLink('S-0907', { consents: [...REQUIRED], notice_version: 'notice-0' })).rejects.toMatchObject({ status: 422, fields: { notice_version: 'out of date' } })
  })

  it('records the ticks when the link is paid: PAYMENT_APP at the request time, the slip left NOT_GIVEN (AC-N6-08)', async () => {
    const { api } = await ramesh()
    const { premium } = await api.premiumLink('S-0907', { consents: [...REQUIRED], notice_version: 'notice-1' })
    expect(granted(backend)).toEqual([])
    await api.paytmWebhook(premium?.link_id ?? '')
    const [sales, slip, settlement] = await api.consents('S-0907')
    for (const item of [sales, settlement]) {
      expect(item).toMatchObject({ status: 'ACTIVE', source: 'PAYMENT_APP', notice_version: 'notice-1', granted_at: '2025-08-18T18:00:00+05:30' })
    }
    expect(slip).toMatchObject({ status: 'NOT_GIVEN', consent_id: null, source: null })
    expect(granted(backend).map((e) => e.data)).toEqual([
      expect.objectContaining({ merchant_id: 'S-0907', purpose: 'SALES_DATA_FOR_CLAIM', source: 'PAYMENT_APP', notice_version: 'notice-1' }),
      expect.objectContaining({ merchant_id: 'S-0907', purpose: 'SETTLEMENT_DEDUCTION', source: 'PAYMENT_APP', notice_version: 'notice-1' }),
    ])
  })

  it('grants the optional slip purpose too when it was ticked', async () => {
    const { api } = await ramesh()
    const { premium } = await api.premiumLink('S-0907', { consents: [...REQUIRED, 'SLIP_DATA_FOR_HOSPITAL_CLAIM'], notice_version: 'notice-1' })
    await api.paytmWebhook(premium?.link_id ?? '')
    expect((await api.consents('S-0907')).map((c) => c.status)).toEqual(['ACTIVE', 'ACTIVE', 'ACTIVE'])
  })

  it('grants sales and settlement as PAYMENT_CHAT for a link the merchant asked for in the chat', async () => {
    const { api } = await ramesh()
    await api.sendText('S-0907', 'mujhe cover chahiye')
    const link = backend.runtime.premiums.at(-1)
    expect(link).toBeDefined()
    await api.paytmWebhook(link?.link_id ?? '')
    const [sales, slip, settlement] = await api.consents('S-0907')
    expect(sales).toMatchObject({ status: 'ACTIVE', source: 'PAYMENT_CHAT', notice_version: null })
    expect(settlement).toMatchObject({ status: 'ACTIVE', source: 'PAYMENT_CHAT' })
    expect(slip.status).toBe('NOT_GIVEN')
  })

  it('lets a merchant with live cover renew without the block', async () => {
    const { api } = await ramesh()
    await expect(api.premiumLink('S-0142')).resolves.toMatchObject({ quote: { merchant_id: 'S-0142' } })
  })
})

describe('POST /api/premium/link with n6_consents off', () => {
  it('ignores the block, as today', async () => {
    const { api } = await ramesh('')
    await expect(api.premiumLink('S-0907')).resolves.toMatchObject({ quote: { outcome: 'BLOCKED' } })
  })
})
