/**
 * `fetch` replacement for mock mode (binding decision B7: VITE_MOCK=1 or ?mock=1). It answers the
 * SPEC §19 routes with real `Response` objects — envelopes for JSON routes and a streaming
 * `text/event-stream` body for /api/stream (resuming after `Last-Event-ID`) — so the production
 * client, SSE parser and reconnect logic run unchanged against the mock.
 */
import type { FetchLike } from '../api/client'
import type { SseEvent } from '../api/types'
import { MockBackend, MockHttpError } from './backend'
import { matchRoute } from './routes'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

function envelope(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS })
}

export function formatSse(event: SseEvent): string {
  return `id: ${event.id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`
}

const noop = (): void => undefined

function streamResponse(backend: MockBackend, headers: Headers, signal: AbortSignal | undefined): Response {
  const encoder = new TextEncoder()
  let unsubscribe: () => void = noop
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      let open = true
      const close = (reason: Error) => {
        if (!open) return
        open = false
        unsubscribe()
        controller.error(reason)
      }
      controller.enqueue(encoder.encode(': connected\n\n'))
      for (const event of backend.eventsAfter(headers.get('Last-Event-ID'))) controller.enqueue(encoder.encode(formatSse(event)))
      unsubscribe = backend.subscribe(
        (event) => {
          if (open) controller.enqueue(encoder.encode(formatSse(event)))
        },
        () => close(new TypeError('mock stream dropped')),
      )
      signal?.addEventListener('abort', () => close(new DOMException('Aborted', 'AbortError')))
    },
    cancel() {
      unsubscribe()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

async function readBody(init: RequestInit | undefined): Promise<{ body: unknown; form: FormData | null }> {
  const raw = init?.body
  if (raw instanceof FormData) return { body: null, form: raw }
  if (typeof raw !== 'string') return { body: null, form: null }
  try {
    return { body: JSON.parse(raw) as unknown, form: null }
  } catch {
    throw new MockHttpError('VALIDATION_ERROR', 'Body must be JSON', 400)
  }
}

export function createMockFetch(backend: MockBackend): FetchLike {
  return async (input, init) => {
    if (backend.isDown()) throw new TypeError('Failed to fetch (mock outage)')
    const url = new URL(input, 'http://mock.local')
    const method = (init?.method ?? 'GET').toUpperCase()
    const headers = new Headers(init?.headers)
    if (method === 'GET' && url.pathname === '/api/stream') return streamResponse(backend, headers, init?.signal ?? undefined)
    const route = matchRoute(method, url.pathname)
    if (!route) return envelope(404, { ok: false, error: { code: 'NOT_FOUND', message: `No route for ${method} ${url.pathname}` } })
    try {
      const { body, form } = await readBody(init)
      const result = await route.handler({ params: route.params, query: url.searchParams, body, form, headers, backend })
      return envelope(200, { ok: true, data: result.data, ...(result.meta ? { meta: result.meta } : {}) })
    } catch (error) {
      if (error instanceof MockHttpError) {
        const fields = Object.keys(error.fields).length > 0 ? { fields: error.fields } : {}
        return envelope(error.status, { ok: false, error: { code: error.code, message: error.message, ...fields } })
      }
      console.error('[mock] handler failed', error)
      return envelope(500, { ok: false, error: { code: 'INTERNAL', message: 'Mock backend error' } })
    }
  }
}
