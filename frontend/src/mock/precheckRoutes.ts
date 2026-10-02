/**
 * Mock routes of N3 (data-model 5.3): POST /api/merchants/{id}/slip-precheck reads a slip and runs the gate, and
 * .../{precheck_id}/confirm confirms it or sends it to the team. Behind `n3_slip_precheck` (404 while off). A silence
 * check-in must be open and no claim filed yet (409 `conflict` otherwise); at most three photos; a new photo
 * supersedes the open check; an upload that is not one of the sample slips reads as unreadable, as in the backend.
 */
import type { Message, PrecheckConfirm, SlipPrecheck } from '../api/types'
import { isFeatureEnabled } from '../features'
import { bodyField, invalid, merchantParam, notFound, ok, type Route, type RouteContext, type RouteResult } from './http'
import { buildPrecheck, conflict, MAX_PHOTOS, prechecksOf, savePrechecks, type SlipReading, type StoredPrecheck } from './precheck'
import { requireSlipConsent } from './endpoints/consents'
import { SAMPLE_SLIPS, submitSlip } from './personal'
import type { MockRuntime } from './runtime'

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
const PRECHECK_ID = /^PC-\d{6}$/
const ACTIONS = ['CONFIRM', 'SEND_TO_TEAM'] as const
const UNREADABLE: SlipReading = { ...SAMPLE_SLIPS['blurry_slip.png'], document_type: null, confidence: 0.22 }

function requireFlag(): void {
  if (!isFeatureEnabled('n3_slip_precheck')) throw notFound('route')
}

function sniff(bytes: Uint8Array): boolean {
  const ascii = (from: number, to: number) => String.fromCharCode(...bytes.slice(from, to))
  return (bytes[0] === 0x89 && ascii(1, 4) === 'PNG') || (bytes[0] === 0xff && bytes[1] === 0xd8) || (ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP')
}

function mediaUrlOf(file: Blob): string {
  try {
    return URL.createObjectURL(file)
  } catch {
    return '/slips/uploaded'
  }
}

type Picked = { sample: string | null; read: SlipReading; mediaUrl: string }

async function pickSlip(ctx: RouteContext, rt: MockRuntime): Promise<Picked> {
  if (ctx.form) {
    const file = ctx.form.get('file')
    if (!(file instanceof Blob)) throw invalid('file', 'attach a file')
    if (file.size === 0 || file.size > MAX_UPLOAD_BYTES) throw invalid('file', 'must be between 1 byte and 5 MB')
    if (!sniff(new Uint8Array(await file.slice(0, 16).arrayBuffer()))) throw invalid('file', 'photo must be JPEG, PNG or WebP')
    return { sample: null, read: UNREADABLE, mediaUrl: mediaUrlOf(file) }
  }
  const named = bodyField(ctx.body, 'sample')
  const sample = named === undefined ? rt.scenario.slipSample : named
  if (typeof sample !== 'string' || !(sample in SAMPLE_SLIPS)) throw notFound('sample slip')
  const known = SAMPLE_SLIPS[sample]
  // The blurry sample has nothing to read: the reader finds no class and a very low confidence (data-model 5.3).
  const read = known.patient_name || known.admission_date ? known : UNREADABLE
  return { sample, read, mediaUrl: `/slips/${sample}` }
}

function checkLang(ctx: RouteContext): void {
  const lang = ctx.form ? ctx.form.get('lang') : bodyField(ctx.body, 'lang')
  if (lang !== undefined && lang !== null && lang !== 'hi' && lang !== 'en') throw invalid('lang', 'hi or en')
}

async function postPrecheck(ctx: RouteContext): Promise<RouteResult> {
  requireFlag()
  const merchant = merchantParam(ctx)
  const rt = ctx.backend.runtime
  const conv = rt.conversation(merchant.id)
  if (!conv.checkinSent || conv.claimId !== null) throw conflict('no silence check-in is open for this merchant')
  checkLang(ctx)
  const consent = ctx.form ? ctx.form.get('consent') === 'true' : bodyField(ctx.body, 'consent')
  const noticeVersion = ctx.form ? ctx.form.get('notice_version') : bodyField(ctx.body, 'notice_version')
  requireSlipConsent(rt, merchant, consent, noticeVersion)
  const before = prechecksOf(rt, merchant.id)
  if (before.photos >= MAX_PHOTOS) throw conflict('three photos have been sent for this check-in')
  const picked = await pickSlip(ctx, rt)
  const id = rt.nextId('PC')
  const view = buildPrecheck({ rt, merchantId: merchant.id, id, mediaId: rt.nextId('MD'), attempt: before.photos + 1, read: picked.read })
  const superseded = [...before.checks].map(([key, old]): [string, StoredPrecheck] => [key, old.view.status === 'CONFIRMED' ? old : { ...old, view: { ...old.view, status: 'SUPERSEDED' } }])
  savePrechecks(rt, merchant.id, { photos: view.attempt, checks: new Map([...superseded, [id, { view, mediaUrl: picked.mediaUrl, sample: picked.sample, confirmed: false }]]) })
  rt.record('ai-agent', 'precheck.shown', 'precheck', id, { precheck_id: id, status: view.status, reason: view.reason, attempt: view.attempt, mode: view.mode, provider: view.provider })
  return ok(view)
}

function actionOf(ctx: RouteContext): (typeof ACTIONS)[number] {
  const action = bodyField(ctx.body, 'action')
  if (typeof action !== 'string' || !(ACTIONS as readonly string[]).includes(action)) throw invalid('action', 'CONFIRM or SEND_TO_TEAM')
  return action as (typeof ACTIONS)[number]
}

function claimOutcome(rt: MockRuntime, merchantId: string, before: number): Omit<PrecheckConfirm, 'precheck_id' | 'status' | 'confirmed_as'> {
  const claimId = rt.conversation(merchantId).claimId
  const decision = rt.decisions.find((d) => d.claim_id === claimId)
  if (!claimId || !decision) throw new Error('the slip claim was not decided')
  const kase = rt.cases.find((c) => c.kind !== 'DISPUTE' && c.decision?.claim_id === claimId) ?? null
  const messages = rt.messages.slice(before).filter((m: Message) => m.merchant_id === merchantId)
  return { claim_id: claimId, decision_id: decision.id, outcome: decision.outcome, case_id: kase?.id ?? null, messages }
}

function confirmPrecheck(ctx: RouteContext): RouteResult {
  requireFlag()
  const merchant = merchantParam(ctx)
  const rt = ctx.backend.runtime
  const action = actionOf(ctx)
  const found = PRECHECK_ID.test(ctx.params[1]) ? prechecksOf(rt, merchant.id).checks.get(ctx.params[1]) : undefined
  if (!found) throw notFound(`pre-check ${ctx.params[1]}`)
  const { status } = found.view
  if (status === 'CONFIRMED' || status === 'SUPERSEDED') throw conflict(`this pre-check is ${status.toLowerCase()}`)
  if (action === 'CONFIRM' && status !== 'READY') throw conflict('only a READY pre-check can be confirmed')
  if (action === 'SEND_TO_TEAM' && status === 'READY') throw conflict('a READY pre-check is confirmed, not sent to the team')
  const conv = rt.conversation(merchant.id)
  if (!conv.checkinSent || conv.claimId !== null) throw conflict('the claim was already filed')
  const before = rt.messages.length
  // The merchant never edits a value: CONFIRM files the slip as read, SEND_TO_TEAM files the empty read (referred).
  submitSlip(rt, merchant, found.mediaUrl, action === 'CONFIRM' ? found.sample : null)
  const outcome = claimOutcome(rt, merchant.id, before)
  const confirmedAs = action === 'CONFIRM' ? 'FIELDS_CONFIRMED' : 'SENT_TO_TEAM'
  const mine = prechecksOf(rt, merchant.id)
  const updated: StoredPrecheck = { ...found, confirmed: true, view: { ...found.view, status: 'CONFIRMED' } satisfies SlipPrecheck }
  savePrechecks(rt, merchant.id, { ...mine, checks: new Map([...mine.checks, [found.view.precheck_id, updated]]) })
  rt.record(`merchant:${merchant.id}`, 'precheck.confirmed', 'precheck', found.view.precheck_id, { precheck_id: found.view.precheck_id, action, claim_id: outcome.claim_id })
  return ok({ precheck_id: found.view.precheck_id, status: 'CONFIRMED', confirmed_as: confirmedAs, ...outcome } satisfies PrecheckConfirm)
}

export const PRECHECK_ROUTES: readonly Route[] = [
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/slip-precheck$/, handler: postPrecheck },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/slip-precheck\/(PC-\d+)\/confirm$/, handler: confirmPrecheck },
]
