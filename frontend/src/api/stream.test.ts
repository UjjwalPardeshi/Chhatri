import { afterEach, describe, expect, it, vi } from 'vitest'

import type { FetchLike } from './client'
import { decodeEvent, EventStream, type StreamStatus } from './stream'
import type { SseEvent } from './types'

const CLOCK = { now: '2025-08-19T17:00:00+05:30', scenario: 'monsoon', scenario_title: 'Monsoon replay', running: false, speed: 6, start: '', end: '', label: 'x' }

function frame(id: number, type = 'tick'): string {
  return `id: ${id}\nevent: ${type}\ndata: ${JSON.stringify({ id: String(id), type, at: CLOCK.now, data: { clock: CLOCK } })}\n\n`
}

/** A controllable streaming response. */
function streamingResponse() {
  let controller!: ReadableStreamDefaultController<Uint8Array>
  const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) })
  const encoder = new TextEncoder()
  return {
    response: new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
    send: (text: string) => controller.enqueue(encoder.encode(text)),
    fail: () => controller.error(new TypeError('network down')),
    close: () => controller.close(),
  }
}

const options = { baseDelayMs: 10, maxDelayMs: 40, silenceMs: 10_000 }
const tick = () => new Promise((r) => setTimeout(r, 0))

afterEach(() => vi.restoreAllMocks())

describe('decodeEvent', () => {
  it('accepts known types only and validates the payload', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    expect(decodeEvent('tick', JSON.stringify({ id: '1', type: 'tick', at: 'a', data: { clock: CLOCK } }))?.type).toBe('tick')
    expect(decodeEvent('mystery', '{}')).toBeNull()
    expect(decodeEvent('tick', 'not json')).toBeNull()
    expect(decodeEvent('tick', '42')).toBeNull()
    expect(decodeEvent('tick', JSON.stringify({ id: 1 }))).toBeNull()
    expect(decodeEvent('kpis', JSON.stringify({ data: { kpis: {} } }))).toMatchObject({ id: '', at: '' })
  })
})

describe('EventStream (SPEC §19.1 resume with Last-Event-ID)', () => {
  it('delivers events, reconnects with Last-Event-ID and reports status', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const first = streamingResponse()
    const second = streamingResponse()
    const fetcher = vi.fn<FetchLike>().mockResolvedValueOnce(first.response).mockResolvedValueOnce(second.response)
    const events: SseEvent[] = []
    const statuses: StreamStatus[] = []
    const stream = new EventStream(fetcher, '/api/stream', { onEvent: (e) => events.push(e), onStatus: (s) => statuses.push(s) }, options)
    stream.start()
    stream.start()
    await tick()
    first.send(frame(41) + frame(42, 'kpis'))
    await tick()
    expect(events.map((e) => e.id)).toEqual(['41', '42'])
    expect(stream.lastId).toBe('42')
    first.fail()
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    const headers = fetcher.mock.calls[1][1]?.headers as Record<string, string>
    expect(headers['Last-Event-ID']).toBe('42')
    second.send(frame(43))
    await vi.waitFor(() => expect(events).toHaveLength(3))
    expect(statuses).toEqual(['connecting', 'open', 'reconnecting', 'open'])
    stream.stop()
    expect(statuses.at(-1)).toBe('closed')
  })

  it('backs off exponentially up to the cap and keeps trying after HTTP errors', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const fetcher = vi.fn<FetchLike>(async () => new Response('down', { status: 503 }))
    const stream = new EventStream(fetcher, '/api/stream', { onEvent: () => undefined, onStatus: () => undefined }, options)
    expect([0, 1, 2, 3].map((a) => stream.delayFor(a))).toEqual([10, 20, 40, 40])
    stream.start()
    await vi.waitFor(() => expect(fetcher.mock.calls.length).toBeGreaterThanOrEqual(3))
    stream.stop()
  })

  it('reconnects when the server ends the stream and after silence', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const ended = streamingResponse()
    const silent = streamingResponse()
    const fetcher = vi.fn<FetchLike>().mockResolvedValueOnce(ended.response).mockResolvedValueOnce(silent.response).mockResolvedValue(streamingResponse().response)
    const stream = new EventStream(fetcher, '/api/stream', { onEvent: () => undefined, onStatus: () => undefined }, { ...options, silenceMs: 30 })
    stream.start()
    await tick()
    ended.close()
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    await vi.waitFor(() => expect(fetcher.mock.calls.length).toBeGreaterThanOrEqual(3), { timeout: 1_000 })
    stream.stop()
  })

  it('never cancels a reader that was already released (late watchdog after the stream ended)', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const ended = streamingResponse()
    const fetcher = vi.fn<FetchLike>().mockResolvedValueOnce(ended.response).mockResolvedValue(new Response(null, { status: 503 }))
    const stream = new EventStream(fetcher, '/api/stream', { onEvent: () => undefined, onStatus: () => undefined }, { ...options, baseDelayMs: 200, maxDelayMs: 200, silenceMs: 30 })
    stream.start()
    await tick()
    ended.close()
    await new Promise((resolve) => setTimeout(resolve, 80))
    stream.stop()
    const messages = warn.mock.calls.map((call) => String(call[0]))
    expect(messages).not.toContain('[stream] cancel failed')
    expect(messages).not.toContain('[stream] no data or keep-alive in time; reconnecting')
  })
})
