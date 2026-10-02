/** The two slip pre-check routes of createApi (data-model 5.3): the paths, the body forms and the client-side checks. */
import { describe, expect, it, vi } from 'vitest'

import { ApiClient, type FetchLike } from './client'
import { createApi } from './endpoints'

function setup() {
  const fetcher = vi.fn<FetchLike>(async () => new Response(JSON.stringify({ ok: true, data: {} })))
  return { api: createApi(new ApiClient(fetcher)), fetcher }
}

const call = (fetcher: ReturnType<typeof setup>['fetcher']) => ({
  url: fetcher.mock.calls[0][0],
  method: fetcher.mock.calls[0][1]?.method,
  body: fetcher.mock.calls[0][1]?.body,
})
const photo = (type = 'image/png', size = 8) => new File([new Uint8Array(size)], 'slip.png', { type })

describe('slip pre-check routes', () => {
  it('posts a sample slip as JSON with the language, and {} for the scenario sample', async () => {
    const { api, fetcher } = setup()
    await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png', lang: 'hi' })
    await api.slipPrecheck('S-0142', {})
    expect(call(fetcher)).toEqual({ url: '/api/merchants/S-0142/slip-precheck', method: 'POST', body: JSON.stringify({ sample: 'anil_admission_slip.png', lang: 'hi' }) })
    expect(fetcher.mock.calls[1][1]?.body).toBe('{}')
  })

  it('posts a photo as a form with a file part and the language', async () => {
    const { api, fetcher } = setup()
    await api.slipPrecheck('S-0142', { file: photo(), lang: 'en' })
    const form = call(fetcher).body as FormData
    expect(form).toBeInstanceOf(FormData)
    expect((form.get('file') as File).name).toBe('slip.png')
    expect(form.get('lang')).toBe('en')
  })

  it('refuses a wrong type, a photo over 5 MB and a malformed id before any request', () => {
    const { api, fetcher } = setup()
    expect(() => api.slipPrecheck('S-0142', { file: photo('application/pdf') })).toThrow(/Invalid input/)
    expect(() => api.slipPrecheck('S-0142', { file: photo('image/png', 5 * 1024 * 1024 + 1) })).toThrow(/Invalid input/)
    expect(() => api.slipPrecheck('S-142', {})).toThrow(/Invalid input/)
    expect(() => api.confirmSlipPrecheck('S-0142', 'PC-1', 'CONFIRM')).toThrow(/Invalid input/)
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('confirms or sends to the team with the action in the body', async () => {
    const { api, fetcher } = setup()
    await api.confirmSlipPrecheck('S-0142', 'PC-000001', 'SEND_TO_TEAM')
    expect(call(fetcher)).toEqual({ url: '/api/merchants/S-0142/slip-precheck/PC-000001/confirm', method: 'POST', body: JSON.stringify({ action: 'SEND_TO_TEAM' }) })
  })
})
