/** The slip pre-check routes and the doctor enrolment routes of createApi (data-model 5.3): the paths, the body forms and the client-side checks. */
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

  it('answers the doctor question with CONSENT_YES or CONSENT_NO, and refuses an unknown action', async () => {
    const { api, fetcher } = setup()
    await api.confirmSlipPrecheck('S-0142', 'PC-000001', 'CONSENT_YES')
    expect(call(fetcher).body).toBe(JSON.stringify({ action: 'CONSENT_YES' }))
    expect(() => api.confirmSlipPrecheck('S-0142', 'PC-000001', 'APPROVE' as never)).toThrow(/Invalid input/)
  })

  it('reads the open pre-check with a GET', async () => {
    const { api, fetcher } = setup()
    await api.openSlipPrecheck('S-0142').catch(() => undefined)
    expect(call(fetcher)).toEqual({ url: '/api/merchants/S-0142/slip-precheck/open', method: 'GET', body: undefined })
  })
})

describe('doctor enrolment routes (officer token)', () => {
  it('posts for the links and for a reset, with the officer token', async () => {
    const { api, fetcher } = setup()
    api.client.setOfficerToken('tok')
    await api.doctorEnrolmentLinks()
    await api.resetDoctorEnrolmentLink('MMC-2011-45817')
    expect(call(fetcher)).toEqual({ url: '/api/doctors/enrolment-links', method: 'POST', body: '{}' })
    expect((fetcher.mock.calls[0][1]?.headers as Record<string, string> | undefined)?.Authorization).toBe('Bearer tok')
    expect(fetcher.mock.calls[1][0]).toBe('/api/doctors/MMC-2011-45817/enrolment-link/reset')
  })

  it('refuses a registration number that does not look like one before any request', () => {
    const { api, fetcher } = setup()
    api.client.setOfficerToken('tok')
    expect(() => api.resetDoctorEnrolmentLink('../x')).toThrow(/Invalid input/)
    expect(fetcher).not.toHaveBeenCalled()
  })
})
