/**
 * What every mock route module shares: the handler and route types and the small helpers that raise the real API's
 * errors (data-model 4.3 and 6.1: lower-case codes, 422 `invalid request` with `fields`, 401 for a missing officer
 * token and 403 for a wrong one, lower-case "merchant S-0001 not found" messages).
 */
import type { ListMeta } from '../api/types'
import type { MockBackend } from './backend'
import { MERCHANTS, MOCK_OFFICER_TOKEN, type MockMerchant } from './fixtures'

export class MockHttpError extends Error {
  readonly code: string
  readonly status: number
  readonly fields: Record<string, string>
  constructor(code: string, message: string, status: number, fields: Record<string, string> = {}) {
    super(message)
    this.code = code
    this.status = status
    this.fields = fields
  }
}

export type RouteContext = {
  params: string[]
  query: URLSearchParams
  body: unknown
  form: FormData | null
  headers: Headers
  backend: MockBackend
}
export type RouteResult = { data: unknown; meta?: ListMeta }
export type Handler = (ctx: RouteContext) => RouteResult | Promise<RouteResult>
export type Route = { method: string; pattern: RegExp; handler: Handler }

export const ok = (data: unknown, meta?: ListMeta): RouteResult => ({ data, meta })

/** `what` reads like the real API: "merchant S-9999", "decision D-000001", "payment link sim-X". */
export const notFound = (what: string): MockHttpError => new MockHttpError('not_found', `${what} not found`, 404)

export const invalid = (field: string, reason: string): MockHttpError =>
  new MockHttpError('validation_error', 'invalid request', 422, { [field]: reason })

export function bodyField(body: unknown, name: string): unknown {
  return typeof body === 'object' && body !== null ? (body as Record<string, unknown>)[name] : undefined
}

export function merchantById(id: string): MockMerchant {
  const merchant = MERCHANTS[id]
  if (!merchant) throw notFound(`merchant ${id}`)
  return merchant
}

export function merchantParam(ctx: RouteContext): MockMerchant {
  return merchantById(ctx.params[0])
}

/** 401 without a bearer token, 403 with a wrong one (backend `require_officer`). */
export function requireOfficer(ctx: RouteContext): void {
  const header = ctx.headers.get('Authorization')
  if (header === null || !header.startsWith('Bearer ')) throw new MockHttpError('unauthorized', 'officer token required', 401)
  if (header !== `Bearer ${MOCK_OFFICER_TOKEN}`) throw new MockHttpError('forbidden', 'invalid officer token', 403)
}
