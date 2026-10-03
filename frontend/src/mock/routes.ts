/**
 * Mock HTTP routes (SPEC §19 table) on top of `MockBackend`. Handlers return the `data` payload
 * (optionally with list `meta`) or throw `MockHttpError`; `fetch.ts` wraps both in the envelope.
 * Inputs are validated like the real API: ids, JSON bodies, officer bearer token, upload type/size
 * by magic bytes (SPEC §21).
 */
import type { CaseStatus, Message, VoiceDemoKey } from '../api/types'
import { enabledFeatures, isFeatureEnabled } from '../features'
import { MockHttpError } from './backend'
import { CaseError, officerDecide } from './cases'
import { inboundPhoto, inboundText, inboundVoiceDemo, inboundVoiceUpload, VOICE_DEMOS } from './conversation'
import { ASK_ROUTES } from './ask'
import { CONSENT_ROUTES } from './endpoints/consents'
import { COVER_ROUTES } from './endpoints/cover'
import { EVALS_ROUTES } from './endpoints/evals'
import { GRIEVANCE_ROUTES } from './endpoints/grievances'
import { OPS_ROUTES } from './endpoints/ops'
import { PREMIUM_ROUTES } from './endpoints/premium'
import { PRICING_ROUTES } from './endpoints/pricing'
import { PRECHECK_ROUTES } from './precheckRoutes'
import { RECEIPT_ROUTES } from './endpoints/receipt'
import { TRACKER_ROUTES } from './endpoints/tracker'
import { WHATIF_ROUTES } from './endpoints/whatif'
import { BACKTEST, integrationRows, MERCHANTS, MOCK_OFFICER_TOKEN, POLICY } from './fixtures'
import { CHANNEL_ROUTES } from './channel'
import { DOCTOR_ROUTES } from './endpoints/doctors'
import { bodyField, invalid, merchantParam, notFound, ok, requireOfficer, type Handler, type Route, type RouteContext, type RouteResult } from './http'
import { SAMPLE_SLIPS } from './personal'
import { GENESIS_HASH } from './runtime'
import { canonicalJson, sha256Hex } from './sha256'
import { merchantDetailView, merchantSummaries, snapshotView, zonePanelView } from './views'

export type { RouteContext, RouteResult } from './http'

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
const MAX_TEXT_CHARS = 1_000
const DEFAULT_AUDIT_LIMIT = 100
const MAX_AUDIT_LIMIT = 500
const CASE_STATUSES: readonly CaseStatus[] = ['OPEN', 'APPROVED', 'DECLINED', 'CLOSED']

/** Magic-byte sniffing (SPEC §21): PNG, JPEG, WebP. */
export function sniffImage(bytes: Uint8Array): string | null {
  const ascii = (from: number, to: number) => String.fromCharCode(...bytes.slice(from, to))
  if (bytes[0] === 0x89 && ascii(1, 4) === 'PNG') return 'image/png'
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg'
  if (ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP') return 'image/webp'
  return null
}

function objectUrl(blob: Blob): string {
  if (typeof URL.createObjectURL !== 'function') throw new MockHttpError('internal', 'Object URLs are not supported here', 500)
  return URL.createObjectURL(blob)
}

function newMessagesSince(ctx: RouteContext, merchantId: string, before: number): RouteResult {
  const all = ctx.backend.runtime.messages
  return ok(all.slice(before).filter((m: Message) => m.merchant_id === merchantId))
}

async function uploadedFile(ctx: RouteContext): Promise<File> {
  const file = ctx.form?.get('file')
  if (!(file instanceof Blob)) throw invalid('file', 'attach a file')
  if (file.size === 0 || file.size > MAX_UPLOAD_BYTES) throw invalid('file', 'must be between 1 byte and 5 MB')
  return file as File
}

async function postPhoto(ctx: RouteContext): Promise<RouteResult> {
  const merchant = merchantParam(ctx)
  const before = ctx.backend.runtime.messages.length
  if (ctx.form) {
    const file = await uploadedFile(ctx)
    const kind = sniffImage(new Uint8Array(await file.slice(0, 16).arrayBuffer()))
    if (!kind) throw invalid('file', 'photo must be JPEG, PNG or WebP')
    inboundPhoto(ctx.backend.runtime, merchant.id, objectUrl(file), null)
    return newMessagesSince(ctx, merchant.id, before)
  }
  const sample = bodyField(ctx.body, 'sample')
  if (typeof sample !== 'string' || !(sample in SAMPLE_SLIPS)) throw invalid('sample', `one of ${Object.keys(SAMPLE_SLIPS).join(', ')}`)
  inboundPhoto(ctx.backend.runtime, merchant.id, `/slips/${sample}`, sample)
  return newMessagesSince(ctx, merchant.id, before)
}

async function postVoice(ctx: RouteContext): Promise<RouteResult> {
  const merchant = merchantParam(ctx)
  const file = await uploadedFile(ctx)
  const before = ctx.backend.runtime.messages.length
  inboundVoiceUpload(ctx.backend.runtime, merchant.id, objectUrl(file))
  return newMessagesSince(ctx, merchant.id, before)
}

function postText(ctx: RouteContext): RouteResult {
  const merchant = merchantParam(ctx)
  const text = bodyField(ctx.body, 'text')
  if (typeof text !== 'string' || text.trim().length === 0) throw invalid('text', 'must not be empty')
  if (text.length > MAX_TEXT_CHARS) throw invalid('text', `at most ${MAX_TEXT_CHARS} characters`)
  const before = ctx.backend.runtime.messages.length
  inboundText(ctx.backend.runtime, merchant.id, text.trim())
  return newMessagesSince(ctx, merchant.id, before)
}

function postVoiceDemo(ctx: RouteContext): RouteResult {
  const merchant = merchantParam(ctx)
  const key = bodyField(ctx.body, 'key')
  if (typeof key !== 'string' || !(key in VOICE_DEMOS)) throw invalid('key', 'one of why, dispute, ill, cover')
  const before = ctx.backend.runtime.messages.length
  inboundVoiceDemo(ctx.backend.runtime, merchant.id, key as VoiceDemoKey)
  return newMessagesSince(ctx, merchant.id, before)
}

function decideCase(approve: boolean): Handler {
  return (ctx) => {
    requireOfficer(ctx)
    const rt = ctx.backend.runtime
    const found = rt.cases.find((c) => c.id === ctx.params[0])
    if (!found) throw notFound(`case ${ctx.params[0]}`)
    const note = bodyField(ctx.body, 'note')
    try {
      return ok(officerDecide(rt, MERCHANTS[found.merchant_id], found.id, approve, typeof note === 'string' ? note : ''))
    } catch (error) {
      if (error instanceof CaseError) throw new MockHttpError(error.code, error.message, error.status)
      throw error
    }
  }
}

function listCases(ctx: RouteContext): RouteResult {
  const status = ctx.query.get('status')
  if (status !== null && !CASE_STATUSES.includes(status as CaseStatus)) throw invalid('status', CASE_STATUSES.join(', '))
  const cases = ctx.backend.runtime.cases.filter((c) => status === null || c.status === status)
  return ok(cases.toReversed())
}

function listAudit(ctx: RouteContext): RouteResult {
  const after = Number(ctx.query.get('after') ?? '0')
  const limit = Number(ctx.query.get('limit') ?? String(DEFAULT_AUDIT_LIMIT))
  if (!Number.isInteger(after) || after < 0) throw invalid('after', 'must be a whole number ≥ 0')
  if (!Number.isInteger(limit) || limit < 1 || limit > MAX_AUDIT_LIMIT) throw invalid('limit', `1–${MAX_AUDIT_LIMIT}`)
  const all = ctx.backend.runtime.audit
  const page = all.filter((e) => e.seq > after).slice(0, limit)
  return ok(page, { total: all.length, limit, offset: after })
}

/** SPEC §11 verify(): recompute every hash and link. */
export function verifyAudit(ctx: RouteContext): RouteResult {
  const entries = ctx.backend.runtime.audit
  let prev = GENESIS_HASH
  for (const entry of entries) {
    const { hash, recorded_at: _recorded, ...body } = entry
    if (body.prev_hash !== prev || sha256Hex(canonicalJson(body)) !== hash) {
      return ok({ valid: false, entries: entries.length, head_hash: entries.at(-1)?.hash ?? GENESIS_HASH, first_bad_seq: entry.seq })
    }
    prev = hash
  }
  return ok({ valid: true, entries: entries.length, head_hash: prev, first_bad_seq: null })
}

function replay(action: (ctx: RouteContext) => unknown): Handler {
  return (ctx) => ok(action(ctx))
}

/** X6 switch (card 4.5): flag-gated, officer-only; only the lender can be forced in the static demo (fs-08 9.7). */
const setFallback: Handler = (ctx) => {
  if (!isFeatureEnabled('x6_provider_panel')) throw notFound('route')
  requireOfficer(ctx)
  const rows = integrationRows(ctx.backend.runtime.lenderForced)
  const row = rows.find((r) => r.name === ctx.params[0])
  if (!row) throw notFound(`component ${ctx.params[0]}`)
  const force = bodyField(ctx.body, 'force')
  if (typeof force !== 'boolean') throw invalid('force', 'must be true or false')
  if (force && !row.switchable) throw new MockHttpError('conflict', 'this component cannot be forced', 409)
  if (row.name === 'lender') ctx.backend.setLenderForced(force)
  return ok(integrationRows(ctx.backend.runtime.lenderForced).find((r) => r.name === row.name))
}

export const ROUTES: readonly Route[] = [
  { method: 'GET', pattern: /^\/api\/health$/, handler: () => ok({ status: 'ok', version: 'mock-console', seed: 20251019, features: enabledFeatures() }) },
  { method: 'GET', pattern: /^\/api\/integrations$/, handler: (c) => ok(integrationRows(c.backend.runtime.lenderForced)) },
  { method: 'POST', pattern: /^\/api\/integrations\/([a-z_]+)\/fallback$/, handler: setFallback },
  { method: 'GET', pattern: /^\/api\/session$/, handler: () => ok({ officer_token: MOCK_OFFICER_TOKEN }) },
  { method: 'GET', pattern: /^\/api\/preflight$/, handler: () => ok([{ name: 'mock', ok: true, detail: 'Mock console backend' }]) },
  { method: 'GET', pattern: /^\/api\/geo\/zones$/, handler: (c) => ok(c.backend.geo.zones) },
  { method: 'GET', pattern: /^\/api\/geo\/hexes$/, handler: (c) => ok(c.backend.geo.hexes) },
  { method: 'GET', pattern: /^\/api\/state$/, handler: (c) => ok(snapshotView(c.backend.runtime, c.backend.geo)) },
  {
    method: 'GET',
    pattern: /^\/api\/zones\/(Z\d+)$/,
    handler: (c) => {
      const zone = c.backend.zones.find((z) => z.id === c.params[0])
      if (!zone) throw notFound(`zone ${c.params[0]}`)
      return ok(zonePanelView(c.backend.runtime, zone))
    },
  },
  { method: 'POST', pattern: /^\/api\/replay\/load$/, handler: replay((c) => c.backend.load(String(bodyField(c.body, 'scenario') ?? ''))) },
  { method: 'POST', pattern: /^\/api\/replay\/play$/, handler: replay((c) => c.backend.play(Number(bodyField(c.body, 'speed') ?? c.backend.runtime.speed))) },
  { method: 'POST', pattern: /^\/api\/replay\/pause$/, handler: replay((c) => c.backend.pause()) },
  { method: 'POST', pattern: /^\/api\/replay\/step$/, handler: replay((c) => c.backend.step(Number(bodyField(c.body, 'minutes')))) },
  { method: 'POST', pattern: /^\/api\/replay\/seek$/, handler: replay((c) => c.backend.seek(String(bodyField(c.body, 'to') ?? ''))) },
  { method: 'POST', pattern: /^\/api\/replay\/reset$/, handler: replay((c) => c.backend.reset()) },
  { method: 'GET', pattern: /^\/api\/merchants$/, handler: () => { const all = merchantSummaries(); return ok(all, { total: all.length, limit: all.length, offset: 0 }) } },
  { method: 'GET', pattern: /^\/api\/merchants\/(S-\d{4})$/, handler: (c) => ok(merchantDetailView(c.backend.runtime, merchantParam(c))) },
  { method: 'GET', pattern: /^\/api\/merchants\/(S-\d{4})\/messages$/, handler: (c) => { const m = merchantParam(c); return ok(c.backend.runtime.messages.filter((x) => x.merchant_id === m.id)) } },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/messages$/, handler: postText },
  ...CHANNEL_ROUTES,
  ...DOCTOR_ROUTES,
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/voice-demo$/, handler: postVoiceDemo },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/voice$/, handler: postVoice },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/photo$/, handler: postPhoto },
  { method: 'GET', pattern: /^\/api\/cases$/, handler: listCases },
  {
    method: 'GET',
    pattern: /^\/api\/cases\/(C-\d+)$/,
    handler: (c) => {
      const found = c.backend.runtime.cases.find((x) => x.id === c.params[0])
      if (!found) throw notFound(`case ${c.params[0]}`)
      return ok(found)
    },
  },
  { method: 'POST', pattern: /^\/api\/cases\/(C-\d+)\/approve$/, handler: decideCase(true) },
  { method: 'POST', pattern: /^\/api\/cases\/(C-\d+)\/decline$/, handler: decideCase(false) },
  {
    method: 'GET',
    pattern: /^\/api\/decisions\/(D-\d+)$/,
    handler: (c) => {
      const found = c.backend.runtime.decisions.find((d) => d.id === c.params[0])
      if (!found) throw notFound(`decision ${c.params[0]}`)
      return ok(found)
    },
  },
  { method: 'GET', pattern: /^\/api\/audit$/, handler: listAudit },
  { method: 'GET', pattern: /^\/api\/audit\/verify$/, handler: verifyAudit },
  { method: 'GET', pattern: /^\/api\/policy$/, handler: () => ok(POLICY) },
  { method: 'GET', pattern: /^\/api\/backtest$/, handler: () => ok(BACKTEST) },
  ...COVER_ROUTES,
  ...TRACKER_ROUTES,
  ...RECEIPT_ROUTES,
  ...PREMIUM_ROUTES,
  ...PRECHECK_ROUTES,
  ...OPS_ROUTES,
  ...WHATIF_ROUTES,
  ...PRICING_ROUTES,
  ...ASK_ROUTES,
  ...GRIEVANCE_ROUTES,
  ...CONSENT_ROUTES,
  ...EVALS_ROUTES,
]

export function matchRoute(method: string, path: string): { handler: Handler; params: string[] } | null {
  for (const route of ROUTES) {
    if (route.method !== method) continue
    const match = route.pattern.exec(path)
    if (match) return { handler: route.handler, params: match.slice(1) }
  }
  return null
}
