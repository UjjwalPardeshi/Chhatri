import { describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError, type FetchLike } from './client'
import { assertMerchantId, clampSpeed, createApi, isHhmm, isScenarioName, MAX_UPLOAD_BYTES, validateAudio, validateImage } from './endpoints'

function setup() {
  const fetcher = vi.fn<FetchLike>(async () => new Response(JSON.stringify({ ok: true, data: {} })))
  const client = new ApiClient(fetcher)
  client.setOfficerToken('t')
  return { api: createApi(client), fetcher }
}

const call = (fetcher: ReturnType<typeof setup>['fetcher'], i = 0) => ({
  url: fetcher.mock.calls[i][0],
  method: fetcher.mock.calls[i][1]?.method,
  body: fetcher.mock.calls[i][1]?.body,
})

describe('endpoint validation (client-side boundary)', () => {
  it('validates ids, scenario names and times', () => {
    expect(assertMerchantId('S-0142')).toBe('S-0142')
    expect(() => assertMerchantId('S-142')).toThrow(/Invalid input/)
    expect(isScenarioName('monsoon')).toBe(true)
    expect(isScenarioName('storm')).toBe(false)
    expect(isHhmm('17:05')).toBe(true)
    expect(isHhmm('24:00')).toBe(false)
    expect(isHhmm('7:05')).toBe(false)
  })

  it('clamps speed to 1–120', () => {
    expect(clampSpeed(0)).toBe(1)
    expect(clampSpeed(6.4)).toBe(6)
    expect(clampSpeed(500)).toBe(120)
    expect(() => clampSpeed(Number.NaN)).toThrow(ApiError)
  })

  it('checks uploads', () => {
    expect(() => validateImage(new File(['x'], 'a.gif', { type: 'image/gif' }))).toThrow(ApiError)
    expect(() => validateImage(new File([new Uint8Array(MAX_UPLOAD_BYTES + 1)], 'a.png', { type: 'image/png' }))).toThrow(ApiError)
    expect(() => validateImage(new File(['x'], 'a.png', { type: 'image/png' }))).not.toThrow()
    expect(() => validateAudio(new Blob([]))).toThrow(/Invalid input/)
    expect(() => validateAudio(new Blob([new Uint8Array(MAX_UPLOAD_BYTES + 1)]))).toThrow(ApiError)
  })
})

describe('createApi routes (SPEC §19 table)', () => {
  it('maps replay controls', async () => {
    const { api, fetcher } = setup()
    await api.load('monsoon')
    await api.play(500)
    await api.step(15)
    await api.seek('17:05')
    await api.pause()
    await api.reset()
    expect(call(fetcher, 0)).toEqual({ url: '/api/replay/load', method: 'POST', body: '{"scenario":"monsoon"}' })
    expect(call(fetcher, 1).body).toBe('{"speed":120}')
    expect(call(fetcher, 2).body).toBe('{"minutes":15}')
    expect(call(fetcher, 3).body).toBe('{"to":"17:05"}')
    expect(call(fetcher, 4).url).toBe('/api/replay/pause')
    expect(call(fetcher, 5).url).toBe('/api/replay/reset')
    expect(() => api.load('storm')).toThrow(ApiError)
    expect(() => api.step(0)).toThrow(ApiError)
    expect(() => api.seek('5pm')).toThrow(ApiError)
  })

  it('maps merchant, case and record routes', async () => {
    const { api, fetcher } = setup()
    await api.merchant('S-0142')
    await api.messages('S-0142')
    await api.sendText('S-0142', '  hello  ')
    await api.sendVoiceDemo('S-0142', 'why')
    await api.sendSampleSlip('S-0142', 'anil_admission_slip.png')
    await api.cases('OPEN')
    await api.cases('ALL')
    await api.caseDetail('C-2291')
    await api.approve('C-2291', 'ok')
    await api.decline('C-2291', '')
    await api.audit(5, 100)
    await api.verifyAudit()
    await api.policy()
    await api.backtest()
    await api.zonePanel('Z7')
    await api.decision('D-000001')
    const urls = fetcher.mock.calls.map((c) => c[0])
    expect(urls).toEqual([
      '/api/merchants/S-0142',
      '/api/merchants/S-0142/messages',
      '/api/merchants/S-0142/messages',
      '/api/merchants/S-0142/voice-demo',
      '/api/merchants/S-0142/photo',
      '/api/cases?status=OPEN',
      '/api/cases',
      '/api/cases/C-2291',
      '/api/cases/C-2291/approve',
      '/api/cases/C-2291/decline',
      '/api/audit?after=5&limit=100',
      '/api/audit/verify',
      '/api/policy',
      '/api/backtest',
      '/api/zones/Z7',
      '/api/decisions/D-000001',
    ])
    expect(call(fetcher, 2).body).toBe('{"text":"hello"}')
    expect(call(fetcher, 4).body).toBe('{"sample":"anil_admission_slip.png"}')
    expect(() => api.sendText('S-0142', '   ')).toThrow(ApiError)
    expect(() => api.zonePanel('7')).toThrow(ApiError)
    expect(() => api.caseDetail('2291')).toThrow(ApiError)
  })

  it('uploads voice and photos as multipart', async () => {
    const { api, fetcher } = setup()
    await api.sendVoice('S-0142', new Blob(['a'], { type: 'audio/webm' }), 'voice-note.webm')
    await api.sendPhoto('S-0142', new File(['x'], 'slip.png', { type: 'image/png' }))
    expect(fetcher.mock.calls[0][1]?.body).toBeInstanceOf(FormData)
    expect(call(fetcher, 1).url).toBe('/api/merchants/S-0142/photo')
  })

  it('reads static info', async () => {
    const { api, fetcher } = setup()
    await api.integrations()
    await api.session()
    await api.state()
    await api.zonesGeo()
    await api.hexesGeo()
    await api.merchants('zone_id=Z7')
    expect(fetcher.mock.calls.map((c) => c[0])).toEqual(['/api/integrations', '/api/session', '/api/state', '/api/geo/zones', '/api/geo/hexes', '/api/merchants?zone_id=Z7'])
  })
})
