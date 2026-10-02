/** Mock HTTP surface (SPEC §19): envelopes, validation, auth, uploads, SSE resume and outages. */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import type { MockBackend } from './backend'
import { createMockFetch, formatSse } from './fetch'
import { MOCK_OFFICER_TOKEN } from './fixtures'
import { sniffImage } from './routes'
import { testApi } from './testkit'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

function setup() {
  const kit = testApi()
  backend = kit.backend
  return kit
}

const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0, 0, 0, 0])

describe('mock routes', () => {
  it('serves the static routes', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = setup()
    expect((await api.integrations()).every((i) => i.mode === 'SIMULATED')).toBe(true)
    expect(await api.session()).toEqual({ officer_token: MOCK_OFFICER_TOKEN })
    expect((await api.zonesGeo()).features).toHaveLength(24)
    expect((await api.hexesGeo()).features.length).toBeGreaterThan(600)
    expect((await api.policy()).authority).toHaveLength(4)
    expect((await api.backtest()).label).toBe('simulated sales · real Open-Meteo rainfall')
    expect((await api.merchants('')).meta).toEqual({ total: 2, limit: 2, offset: 0 })
    expect(await api.client.get('/api/health')).toEqual({ status: 'ok', version: 'mock-console', seed: 20251019, features: [] })
    expect(await api.client.get('/api/preflight')).toEqual([{ name: 'mock', ok: true, detail: 'Mock console backend' }])
  })

  it('lists the console feature flags that are on in /api/health, sorted, like the backend', async () => {
    vi.stubEnv('VITE_FEATURES', 'n2_ask_chhatri, n1_miniapp, typo')
    const { api } = setup()
    expect(await api.client.get('/api/health')).toMatchObject({ status: 'ok', features: ['n1_miniapp', 'n2_ask_chhatri'] })
  })

  it('drives the replay and returns clock states', async () => {
    const { api } = setup()
    expect((await api.state()).clock.now).toBe('2025-08-19T08:00:00+05:30')
    expect((await api.seek('17:05')).label).toBe('Mumbai · monsoon replay · 17:05 · simulated')
    expect((await api.step(10)).now).toBe('2025-08-19T17:15:00+05:30')
    expect((await api.zonePanel('Z7')).rows[0].value).toBe('Red alert from 14:00')
    expect((await api.load('buy_cover')).scenario).toBe('buy_cover')
    expect((await api.reset()).now).toBe('2025-08-18T18:00:00+05:30')
    await expect(api.seek('09:00')).rejects.toMatchObject({ code: 'VALIDATION_ERROR', fields: { to: 'must be between 18:00 and 19:00' } })
    await expect(api.client.post('/api/replay/load', { scenario: 'storm' })).rejects.toMatchObject({ fields: { scenario: 'unknown scenario' } })
    await expect(api.client.post('/api/replay/step', { minutes: 0 })).rejects.toMatchObject({ status: 422 })
    await expect(api.client.post('/api/replay/play', { speed: 900 })).rejects.toMatchObject({ fields: { speed: 'must be between 1 and 120' } })
  })

  it('handles merchants, messages and cases end to end', async () => {
    const { api, client } = setup()
    await api.seek('17:05')
    const detail = await api.merchant('S-0142')
    expect(detail).toMatchObject({ expected_today_label: '₹4,380', loan: { daily_instalment_label: '₹600' }, cover: { status: 'ACTIVE' } })
    expect(detail.payouts[0].amount_label).toBe('₹1,380')
    const sent = (await api.sendVoiceDemo('S-0142', 'why')) as { text_en: string }[]
    expect(sent.at(-1)?.text_en).toMatch(/^Your usual Tuesday/)
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    expect((await api.cases('OPEN')).map((c) => c.id)).toEqual(['C-2291'])
    await expect(api.approve('C-2291', '')).rejects.toMatchObject({ code: 'NO_OFFICER_TOKEN' })
    client.setOfficerToken('wrong')
    await expect(api.approve('C-2291', '')).rejects.toMatchObject({ code: 'UNAUTHORIZED', status: 401 })
    client.setOfficerToken(MOCK_OFFICER_TOKEN)
    expect((await api.approve('C-2291', 'fine')).case.status).toBe('CLOSED')
    await expect(api.decline('C-2291', '')).rejects.toMatchObject({ code: 'CONFLICT', status: 409 })
    expect((await api.caseDetail('C-2291')).resolution).toBe('fine')
    expect(await api.cases('ALL')).toHaveLength(1)
    await expect(api.caseDetail('C-1')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(api.approve('C-1', '')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(api.client.get('/api/cases?status=WEIRD')).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
    expect((await api.decision('D-000001')).amount_label).toBe('₹1,380')
    await expect(api.decision('D-999999')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(api.merchant('S-0001')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(api.zonePanel('Z99')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(api.client.get('/api/nothing')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(api.client.post('/api/merchants/S-0142/messages', { text: 'x'.repeat(1001) })).rejects.toMatchObject({ fields: { text: 'at most 1000 characters' } })
    await expect(api.client.post('/api/merchants/S-0142/voice-demo', { key: 'sing' })).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
  })

  it('checks uploads by magic bytes and handles slips', async () => {
    const { api } = setup()
    await api.load('illness')
    await api.seek('11:20')
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:mock' }))
    await expect(api.sendPhoto('S-0142', new File(['GIF89a'], 'x.png', { type: 'image/png' }))).rejects.toMatchObject({ fields: { file: 'photo must be JPEG, PNG or WebP' } })
    await api.sendVoice('S-0142', new Blob(['voice'], { type: 'audio/webm' }), 'voice-note.webm')
    const reply = (await api.sendPhoto('S-0142', new File([PNG], 'slip.png', { type: 'image/png' }))) as { kind: string }[]
    expect(reply[0].kind).toBe('IMAGE')
    await expect(api.sendSampleSlip('S-0142', 'selfie.png')).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
    await expect(api.client.postForm('/api/merchants/S-0142/voice', new FormData())).rejects.toMatchObject({ fields: { file: 'attach a file' } })
    vi.unstubAllGlobals()
  })

  it('sniffs image types', () => {
    expect(sniffImage(PNG)).toBe('image/png')
    expect(sniffImage(new Uint8Array([0xff, 0xd8, 0xff, 0xe0]))).toBe('image/jpeg')
    expect(sniffImage(new TextEncoder().encode('RIFF1234WEBPVP8 '))).toBe('image/webp')
    expect(sniffImage(new TextEncoder().encode('GIF89a'))).toBeNull()
  })

  it('pages the audit log and verifies the chain', async () => {
    const { api } = setup()
    await api.seek('17:05')
    const first = await api.audit(0, 5)
    expect(first.items.map((e) => e.seq)).toEqual([1, 2, 3, 4, 5])
    expect(first.meta?.total).toBeGreaterThan(5)
    expect((await api.audit(5, 2)).items[0].seq).toBe(6)
    expect(await api.verifyAudit()).toMatchObject({ valid: true, first_bad_seq: null })
    const entries = backend.runtime.audit
    entries[2] = { ...entries[2], data: { tampered: true } }
    expect(await api.verifyAudit()).toMatchObject({ valid: false, first_bad_seq: 3 })
    await expect(api.audit(-1, 5)).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
    await expect(api.audit(0, 5000)).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
  })

  it('rejects non-JSON bodies and reports handler crashes as INTERNAL', async () => {
    const { backend: b } = setup()
    const fetcher = createMockFetch(b)
    const bad = await fetcher('/api/replay/load', { method: 'POST', body: '{nope' })
    expect(await bad.json()).toMatchObject({ ok: false, error: { code: 'VALIDATION_ERROR' } })
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    vi.spyOn(b, 'pause').mockImplementation(() => {
      throw new Error('boom')
    })
    const crash = await fetcher('/api/replay/pause', { method: 'POST' })
    expect(crash.status).toBe(500)
    expect(await crash.json()).toEqual({ ok: false, error: { code: 'INTERNAL', message: 'Mock backend error' } })
  })
})

async function readSome(response: Response, count: number): Promise<string> {
  const reader = response.body?.getReader()
  if (!reader) throw new Error('no body')
  const decoder = new TextDecoder()
  let text = ''
  while ((text.match(/\n\n/g) ?? []).length < count) {
    const { value, done } = await reader.read()
    if (done) break
    text += decoder.decode(value)
  }
  reader.releaseLock()
  return text
}

describe('mock SSE', () => {
  it('resumes after Last-Event-ID and streams new events', async () => {
    const { backend: b } = setup()
    const fetcher = createMockFetch(b)
    const lastId = Number(b.eventsAfter('0').at(-1)?.id)
    b.step(1)
    const response = await fetcher('/api/stream', { headers: { 'Last-Event-ID': String(lastId) } })
    expect(response.headers.get('Content-Type')).toBe('text/event-stream')
    const text = await readSome(response, 2)
    expect(text).toContain(': connected')
    expect(text).toContain(`id: ${lastId + 1}\n`)
    expect(b.eventsAfter(null)).toEqual([])
    expect(b.eventsAfter('abc')).toEqual([])
  })

  it('formats frames with id, event and JSON data', () => {
    expect(formatSse({ id: '5', type: 'kpis', at: 'a', data: { kpis: {} as never } })).toBe('id: 5\nevent: kpis\ndata: {"id":"5","type":"kpis","at":"a","data":{"kpis":{}}}\n\n')
  })

  it('drops streams and refuses connections during an outage', async () => {
    const { backend: b } = setup()
    const fetcher = createMockFetch(b)
    const response = await fetcher('/api/stream', {})
    const reader = response.body?.getReader()
    await reader?.read()
    b.outage(60_000)
    await expect(reader?.read()).rejects.toThrow(/dropped/)
    await expect(fetcher('/api/state', {})).rejects.toThrow(/outage/)
    expect(b.isDown()).toBe(true)
  })

  it('closes the stream when the client aborts', async () => {
    const { backend: b } = setup()
    const controller = new AbortController()
    const response = await createMockFetch(b)('/api/stream', { signal: controller.signal })
    const reader = response.body?.getReader()
    await reader?.read()
    controller.abort()
    await expect(reader?.read()).rejects.toThrow(/Aborted/)
  })
})

describe('ApiError from mock', () => {
  it('is a real ApiError', async () => {
    const { api } = setup()
    await expect(api.merchant('S-0001')).rejects.toBeInstanceOf(ApiError)
  })
})
