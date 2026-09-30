import { describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError, REQUEST_TIMEOUT_MS, unwrapEnvelope, type FetchLike } from './client'

/** Runs `fn`, which must throw an ApiError, and returns that error. */
function caught(fn: () => unknown): ApiError {
  try {
    fn()
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error('expected an ApiError')
}

const hanging: FetchLike = (_url, init) =>
  new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))

const failing = () => unwrapEnvelope({ ok: false, error: { code: 'VALIDATION_ERROR', message: 'Invalid input', fields: { to: 'use HH:MM' } } }, 422)

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('unwrapEnvelope (SPEC §19 envelope)', () => {
  it('returns data and list meta', () => {
    expect(unwrapEnvelope({ ok: true, data: [1] }, 200)).toEqual({ data: [1], meta: null })
    expect(unwrapEnvelope({ ok: true, data: [], meta: { total: 3, limit: 1, offset: 0 } }, 200).meta).toEqual({ total: 3, limit: 1, offset: 0 })
  })

  it('surfaces error.code, message and fields', () => {
    expect(failing).toThrow(ApiError)
    const e = caught(failing)
    expect([e.code, e.message, e.status, e.fields]).toEqual(['VALIDATION_ERROR', 'Invalid input', 422, { to: 'use HH:MM' }])
    expect(e.describe()).toBe('Invalid input (to: use HH:MM)')
  })

  it('rejects malformed bodies', () => {
    expect(() => unwrapEnvelope({ data: 1 }, 200)).toThrow(/Unexpected response/)
    expect(() => unwrapEnvelope(null, 502)).toThrow(/HTTP 502/)
    expect(() => unwrapEnvelope({ ok: false, error: 'boom' }, 500)).toThrow(/Malformed error/)
  })
})

describe('ApiClient', () => {
  it('GETs and unwraps', async () => {
    const fetcher = vi.fn<FetchLike>(async () => json({ ok: true, data: { status: 'ok' } }))
    const client = new ApiClient(fetcher, 'http://api')
    await expect(client.get('/api/health')).resolves.toEqual({ status: 'ok' })
    expect(fetcher.mock.calls[0][0]).toBe('http://api/api/health')
    expect(fetcher.mock.calls[0][1]?.method).toBe('GET')
  })

  it('lists with meta', async () => {
    const client = new ApiClient(async () => json({ ok: true, data: [1, 2], meta: { total: 2, limit: 2, offset: 0 } }))
    await expect(client.list('/api/audit')).resolves.toEqual({ items: [1, 2], meta: { total: 2, limit: 2, offset: 0 } })
  })

  it('POSTs JSON and sends the officer bearer token only when asked', async () => {
    const fetcher = vi.fn<FetchLike>(async () => json({ ok: true, data: {} }))
    const client = new ApiClient(fetcher)
    await expect(client.post('/api/cases/C-1/approve', { note: 'x' }, true)).rejects.toMatchObject({ code: 'NO_OFFICER_TOKEN' })
    expect(client.hasOfficerToken()).toBe(false)
    client.setOfficerToken('secret')
    await client.post('/api/cases/C-1/approve', { note: 'x' }, true)
    const init = fetcher.mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer secret')
    expect(init.body).toBe('{"note":"x"}')
    await client.post('/api/replay/pause')
    const plain = fetcher.mock.calls[1][1] as RequestInit
    expect((plain.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('posts multipart forms without a JSON content type', async () => {
    const fetcher = vi.fn<FetchLike>(async () => json({ ok: true, data: 1 }))
    const form = new FormData()
    form.append('file', new Blob(['x']), 'a.png')
    await new ApiClient(fetcher).postForm('/api/merchants/S-0142/photo', form)
    const init = fetcher.mock.calls[0][1] as RequestInit
    expect(init.body).toBe(form)
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined()
  })

  it('maps error envelopes, bad bodies and network failures', async () => {
    await expect(new ApiClient(async () => json({ ok: false, error: { code: 'NOT_FOUND', message: 'Case C-9 not found' } }, 404)).get('/x')).rejects.toMatchObject({ code: 'NOT_FOUND', status: 404 })
    await expect(new ApiClient(async () => new Response('<html>bad gateway</html>', { status: 502 })).get('/x')).rejects.toMatchObject({ code: 'BAD_RESPONSE', status: 502 })
    await expect(new ApiClient(async () => Promise.reject(new TypeError('Failed to fetch'))).get('/x')).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
    await expect(new ApiClient(async () => Promise.reject('plain')).get('/x')).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
  })

  it('times out slow requests and honours caller aborts', async () => {
    vi.useFakeTimers()
    const pending = new ApiClient(hanging).get('/slow').catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 1)
    expect(await pending).toMatchObject({ code: 'TIMEOUT' })
    const controller = new AbortController()
    const cancelled = new ApiClient(hanging).get('/slow', controller.signal)
    controller.abort()
    await expect(cancelled).rejects.toMatchObject({ code: 'ABORTED' })
  })
})
