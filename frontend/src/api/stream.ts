/**
 * Live event stream (SPEC §19.1, §20 "Resilience"). Uses fetch + a streaming body instead of
 * EventSource so the client can send `Last-Event-ID` itself on every reconnect (EventSource only
 * does that for its own internal retries). Reconnects forever with capped exponential backoff and
 * a silence watchdog (the server pings every 15 s); the UI shows a "reconnecting" pill meanwhile.
 */
import type { FetchLike } from './client'
import { SseParser } from './sse'
import { SSE_EVENT_TYPES, type SseEvent, type SseEventType } from './types'

export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'closed'

export type StreamHandlers = {
  onEvent: (event: SseEvent) => void
  onStatus: (status: StreamStatus) => void
}

export type StreamOptions = {
  baseDelayMs: number
  maxDelayMs: number
  /** No bytes (not even a keep-alive ping) for this long ⇒ reconnect. */
  silenceMs: number
}

export const DEFAULT_STREAM_OPTIONS: StreamOptions = { baseDelayMs: 500, maxDelayMs: 8_000, silenceMs: 45_000 }

const KNOWN_TYPES = new Set<string>(SSE_EVENT_TYPES)

/** Parses one SSE `data:` payload into a typed event; returns null (and logs) when malformed. */
export function decodeEvent(eventName: string, raw: string): SseEvent | null {
  if (!KNOWN_TYPES.has(eventName)) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch (error) {
    console.warn(`[stream] dropped malformed ${eventName} event`, error)
    return null
  }
  if (typeof parsed !== 'object' || parsed === null) return null
  const body = parsed as { id?: unknown; type?: unknown; at?: unknown; data?: unknown }
  if (typeof body.data !== 'object' || body.data === null) {
    console.warn(`[stream] dropped ${eventName} event without data`)
    return null
  }
  return {
    id: String(body.id ?? ''),
    type: eventName as SseEventType,
    at: typeof body.at === 'string' ? body.at : '',
    data: body.data,
  } as SseEvent
}

export class EventStream {
  private lastEventId: string | null = null
  private controller: AbortController | null = null
  private attempt = 0
  private stopped = true
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private silenceTimer: ReturnType<typeof setTimeout> | null = null
  private readonly fetchImpl: FetchLike
  private readonly url: string
  private readonly handlers: StreamHandlers
  private readonly options: StreamOptions

  constructor(fetchImpl: FetchLike, url: string, handlers: StreamHandlers, options = DEFAULT_STREAM_OPTIONS) {
    this.fetchImpl = fetchImpl
    this.url = url
    this.handlers = handlers
    this.options = options
  }

  get lastId(): string | null {
    return this.lastEventId
  }

  start(): void {
    if (!this.stopped) return
    this.stopped = false
    this.handlers.onStatus('connecting')
    void this.connect()
  }

  stop(): void {
    this.stopped = true
    this.clearTimers()
    this.controller?.abort()
    this.controller = null
    this.handlers.onStatus('closed')
  }

  /** Next backoff delay: base × 2^attempt, capped. */
  delayFor(attempt: number): number {
    return Math.min(this.options.maxDelayMs, this.options.baseDelayMs * 2 ** attempt)
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = { Accept: 'text/event-stream', 'Cache-Control': 'no-cache' }
    if (this.lastEventId) headers['Last-Event-ID'] = this.lastEventId
    return headers
  }

  private async connect(): Promise<void> {
    const controller = new AbortController()
    this.controller = controller
    try {
      const response = await this.fetchImpl(this.url, { headers: this.headers(), signal: controller.signal })
      if (!response.ok || !response.body) throw new Error(`stream HTTP ${response.status}`)
      this.handlers.onStatus('open')
      await this.pump(response.body, controller)
      if (!controller.signal.aborted) console.warn('[stream] server closed the stream; reconnecting')
    } catch (error) {
      if (!controller.signal.aborted || !this.stopped) console.warn('[stream] connection lost', error)
    }
    this.scheduleReconnect(controller)
  }

  private async pump(body: ReadableStream<Uint8Array>, controller: AbortController): Promise<void> {
    const reader = body.getReader()
    const decoder = new TextDecoder()
    const parser = new SseParser()
    /** Set once the lock is released, so a late watchdog never cancels a released reader. */
    const lease = { released: false }
    this.armSilenceWatchdog(controller, reader, lease)
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) return
        this.attempt = 0
        this.armSilenceWatchdog(controller, reader, lease)
        for (const message of parser.push(decoder.decode(value, { stream: true }))) {
          if (message.id !== null) this.lastEventId = message.id
          const event = decodeEvent(message.event, message.data)
          if (event) this.handlers.onEvent(event)
        }
      }
    } finally {
      lease.released = true
      reader.releaseLock()
    }
  }

  /** No bytes for `silenceMs` ⇒ abort the request and cancel the body (works for any stream). */
  private armSilenceWatchdog(controller: AbortController, reader: ReadableStreamDefaultReader<Uint8Array>, lease: { readonly released: boolean }): void {
    if (this.silenceTimer) clearTimeout(this.silenceTimer)
    this.silenceTimer = setTimeout(() => {
      if (lease.released) return
      console.warn('[stream] no data or keep-alive in time; reconnecting')
      controller.abort()
      reader.cancel().catch((error: unknown) => console.warn('[stream] cancel failed', error))
    }, this.options.silenceMs)
  }

  private scheduleReconnect(controller: AbortController): void {
    if (this.stopped || this.controller !== controller) return
    this.clearTimers()
    this.handlers.onStatus('reconnecting')
    const delay = this.delayFor(this.attempt)
    this.attempt += 1
    this.retryTimer = setTimeout(() => void this.connect(), delay)
  }

  private clearTimers(): void {
    if (this.retryTimer) clearTimeout(this.retryTimer)
    if (this.silenceTimer) clearTimeout(this.silenceTimer)
    this.retryTimer = null
    this.silenceTimer = null
  }
}
