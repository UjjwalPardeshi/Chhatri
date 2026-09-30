/**
 * Envelope-aware HTTP client (SPEC §19). Every response is `{ok, data, meta?}` or
 * `{ok: false, error: {code, message, fields?}}`; the client unwraps the envelope and raises
 * `ApiError` carrying `code`, `message`, `fields` and the HTTP status. Transport failures and
 * non-envelope bodies are reported as `NETWORK_ERROR` / `BAD_RESPONSE` — never swallowed.
 */
import type { ApiErrorBody, Envelope, ListMeta } from './types'

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>

export const REQUEST_TIMEOUT_MS = 20_000

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly fields: Readonly<Record<string, string>>

  constructor(code: string, message: string, status: number, fields: Record<string, string> = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.fields = Object.freeze({ ...fields })
  }

  /** One line for an error banner: the message plus any field reasons. */
  describe(): string {
    const extra = Object.entries(this.fields).map(([field, reason]) => `${field}: ${reason}`)
    return extra.length > 0 ? `${this.message} (${extra.join('; ')})` : this.message
  }
}

export type ListResult<T> = { items: T; meta: ListMeta | null }

type RequestOptions = { body?: unknown; form?: FormData; auth?: boolean; signal?: AbortSignal }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseErrorBody(value: unknown): ApiErrorBody | null {
  if (!isRecord(value) || typeof value.code !== 'string' || typeof value.message !== 'string') return null
  const fields = isRecord(value.fields)
    ? Object.fromEntries(Object.entries(value.fields).map(([k, v]) => [k, String(v)]))
    : undefined
  return { code: value.code, message: value.message, fields }
}

/** Validates the §19 envelope shape; throws `ApiError` for error envelopes and malformed bodies. */
export function unwrapEnvelope<T>(body: unknown, status: number): { data: T; meta: ListMeta | null } {
  if (!isRecord(body) || typeof body.ok !== 'boolean') {
    throw new ApiError('BAD_RESPONSE', `Unexpected response from the server (HTTP ${status})`, status)
  }
  const envelope = body as Envelope<T>
  if (!envelope.ok) {
    const error = parseErrorBody(envelope.error)
    if (!error) throw new ApiError('BAD_RESPONSE', `Malformed error from the server (HTTP ${status})`, status)
    throw new ApiError(error.code, error.message, status, error.fields)
  }
  return { data: envelope.data, meta: envelope.meta ?? null }
}

export class ApiClient {
  private token: string | null = null
  private readonly baseUrl: string
  private readonly fetchImpl: FetchLike

  constructor(fetchImpl: FetchLike, baseUrl = '') {
    this.fetchImpl = fetchImpl
    this.baseUrl = baseUrl
  }

  setOfficerToken(token: string | null): void {
    this.token = token
  }

  hasOfficerToken(): boolean {
    return this.token !== null
  }

  url(path: string): string {
    return `${this.baseUrl}${path}`
  }

  get fetcher(): FetchLike {
    return this.fetchImpl
  }

  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    return (await this.send<T>('GET', path, { signal })).data
  }

  async list<T>(path: string, signal?: AbortSignal): Promise<ListResult<T>> {
    const result = await this.send<T>('GET', path, { signal })
    return { items: result.data, meta: result.meta }
  }

  async post<T>(path: string, body: unknown = {}, auth = false): Promise<T> {
    return (await this.send<T>('POST', path, { body, auth })).data
  }

  async postForm<T>(path: string, form: FormData): Promise<T> {
    return (await this.send<T>('POST', path, { form })).data
  }

  private headers(options: RequestOptions): Record<string, string> {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (options.body !== undefined) headers['Content-Type'] = 'application/json'
    if (options.auth) {
      if (!this.token) throw new ApiError('NO_OFFICER_TOKEN', 'Officer token is not available', 401)
      headers.Authorization = `Bearer ${this.token}`
    }
    return headers
  }

  private async send<T>(method: string, path: string, options: RequestOptions) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    const relay = () => controller.abort()
    options.signal?.addEventListener('abort', relay)
    try {
      const response = await this.fetchImpl(this.url(path), {
        method,
        headers: this.headers(options),
        body: options.form ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
        signal: controller.signal,
      })
      return unwrapEnvelope<T>(await readJson(response), response.status)
    } catch (error) {
      throw toApiError(error, controller.signal.aborted && !options.signal?.aborted)
    } finally {
      clearTimeout(timer)
      options.signal?.removeEventListener('abort', relay)
    }
  }
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  try {
    return JSON.parse(text) as unknown
  } catch {
    throw new ApiError('BAD_RESPONSE', `Unexpected response from the server (HTTP ${response.status})`, response.status)
  }
}

function toApiError(error: unknown, timedOut: boolean): ApiError {
  if (error instanceof ApiError) return error
  if (timedOut) return new ApiError('TIMEOUT', 'The server took too long to answer', 0)
  if (error instanceof DOMException && error.name === 'AbortError') {
    return new ApiError('ABORTED', 'Request cancelled', 0)
  }
  const detail = error instanceof Error ? error.message : String(error)
  return new ApiError('NETWORK_ERROR', `Cannot reach the Chhatri server (${detail})`, 0)
}
