/** The mini-app routes of createApi (data-model 5.1, 5.8 and the BUILT premium link and Paytm callback). */
import { describe, expect, it, vi } from 'vitest'

import { ApiClient, type FetchLike } from './client'
import { createApi } from './endpoints'

function setup(token: string | null = 't') {
  const fetcher = vi.fn<FetchLike>(async () => new Response(JSON.stringify({ ok: true, data: [], meta: { total: 0, limit: 0, offset: 0 } })))
  const client = new ApiClient(fetcher)
  client.setOfficerToken(token)
  return { api: createApi(client), fetcher }
}

const sent = (fetcher: ReturnType<typeof setup>['fetcher'], i = 0) => ({
  url: fetcher.mock.calls[i][0],
  method: fetcher.mock.calls[i][1]?.method ?? 'GET',
  body: fetcher.mock.calls[i][1]?.body,
  headers: new Headers(fetcher.mock.calls[i][1]?.headers),
})

describe('mini-app read routes', () => {
  it('asks for the cover, the claims and the receipt of the merchant or decision', async () => {
    const { api, fetcher } = setup()
    await api.cover('S-0142')
    await api.claims('S-0142')
    await api.receipt('D-000142')
    expect(sent(fetcher, 0)).toMatchObject({ url: '/api/merchants/S-0142/cover', method: 'GET' })
    expect(sent(fetcher, 1)).toMatchObject({ url: '/api/merchants/S-0142/claims', method: 'GET' })
    expect(sent(fetcher, 2)).toMatchObject({ url: '/api/decisions/D-000142/receipt', method: 'GET' })
  })

  it('returns the list with its meta for claims', async () => {
    const { api } = setup()
    expect(await api.claims('S-0907')).toEqual({ items: [], meta: { total: 0, limit: 0, offset: 0 } })
  })

  it('refuses a malformed id before any request is made', () => {
    const { api, fetcher } = setup()
    expect(() => api.cover('S-142')).toThrow(/Invalid input/)
    expect(() => api.claims('merchant')).toThrow(/Invalid input/)
    expect(() => api.receipt('D-12')).toThrow(/Invalid input/)
    expect(() => api.receipt('D-000142/../x')).toThrow(/Invalid input/)
    expect(fetcher).not.toHaveBeenCalled()
  })
})

describe('premium link and Paytm callback', () => {
  it('posts the merchant id with the officer token', async () => {
    const { api, fetcher } = setup()
    await api.premiumLink('S-0907')
    const call = sent(fetcher)
    expect(call).toMatchObject({ url: '/api/premium/link', method: 'POST', body: '{"merchant_id":"S-0907"}' })
    expect(call.headers.get('Authorization')).toBe('Bearer t')
  })

  it('needs the officer token for the link, and never sends one to the Paytm callback', async () => {
    const { api, fetcher } = setup(null)
    await expect(api.premiumLink('S-0907')).rejects.toMatchObject({ code: 'NO_OFFICER_TOKEN' })
    await api.paytmWebhook('sim-7BFFBE')
    const call = sent(fetcher)
    expect(call).toMatchObject({ url: '/api/webhooks/paytm', method: 'POST', body: '{"link_id":"sim-7BFFBE","status":"TXN_SUCCESS","txn_id":"SIM-sim-7BFFBE"}' })
    expect(call.headers.get('Authorization')).toBeNull()
  })

  it('refuses a malformed merchant or link id', () => {
    const { api, fetcher } = setup()
    expect(() => api.premiumLink('S-12')).toThrow(/Invalid input/)
    expect(() => api.paytmWebhook('sim 7BFFBE')).toThrow(/Invalid input/)
    expect(() => api.paytmWebhook('')).toThrow(/Invalid input/)
    expect(fetcher).not.toHaveBeenCalled()
  })
})
