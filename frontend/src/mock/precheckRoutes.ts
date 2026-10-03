/**
 * Mock routes of N3 (data-model 5.3, design 2.4): POST /api/merchants/{id}/slip-precheck reads a slip and runs the gate,
 * .../{precheck_id}/confirm confirms it (which asks the doctor question first), answers that question or sends the slip
 * to the team, and GET .../slip-precheck/open says what the open check-in waits on. Behind `n3_slip_precheck` (404
 * while off). A silence check-in must be open and no claim filed yet (409 `no_checkin`); at most three photos (409
 * `photo_limit`); a new photo supersedes the open check; each wrong action has its own 409 code (design 2.3); an
 * upload that is not one of the sample slips reads as unreadable, as in the backend.
 */
import type { DoctorConsent, Message, PrecheckAction, PrecheckConfirm, PrecheckOpen, SlipPrecheck } from '../api/types'
import { PRECHECK_ACTIONS } from '../api/types'
import { isFeatureEnabled } from '../features'
import { bodyField, invalid, merchantParam, notFound, ok, type Route, type RouteContext, type RouteResult } from './http'
import { askConsent, consentView, recordConsent } from './doctor'
import { buildPrecheck, conflict, MAX_PHOTOS, prechecksOf, savePrechecks, type ConflictCode, type SlipReading, type StoredPrecheck } from './precheck'
import { requireSlipConsent } from './endpoints/consents'
import { SAMPLE_SLIPS, submitSlip } from './personal'
import { addDays } from './scenarios'
import type { MockRuntime } from './runtime'

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
const PRECHECK_ID = /^PC-\d{6}$/
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
  if (!conv.checkinSent || conv.claimId !== null) throw conflict('no_checkin', 'no silence check-in is open for this merchant')
  checkLang(ctx)
  const consent = ctx.form ? ctx.form.get('consent') === 'true' : bodyField(ctx.body, 'consent')
  const noticeVersion = ctx.form ? ctx.form.get('notice_version') : bodyField(ctx.body, 'notice_version')
  requireSlipConsent(rt, merchant, consent, noticeVersion)
  const before = prechecksOf(rt, merchant.id)
  if (before.photos >= MAX_PHOTOS) throw conflict('photo_limit', 'three photos have been sent for this check-in')
  const picked = await pickSlip(ctx, rt)
  const id = rt.nextId('PC')
  const view = buildPrecheck({ rt, merchantId: merchant.id, id, mediaId: rt.nextId('MD'), attempt: before.photos + 1, read: picked.read })
  const superseded = [...before.checks].map(([key, old]): [string, StoredPrecheck] => [key, old.view.status === 'CONFIRMED' ? old : { ...old, view: { ...old.view, status: 'SUPERSEDED' } }])
  const stored: StoredPrecheck = { view, mediaUrl: picked.mediaUrl, sample: picked.sample, confirmed: false, read: picked.read }
  savePrechecks(rt, merchant.id, { photos: view.attempt, checks: new Map([...superseded, [id, stored]]) })
  rt.record('ai-agent', 'precheck.shown', 'precheck', id, { precheck_id: id, status: view.status, reason: view.reason, attempt: view.attempt, mode: view.mode, provider: view.provider })
  return ok(view)
}

function actionOf(ctx: RouteContext): PrecheckAction {
  const action = bodyField(ctx.body, 'action')
  if (typeof action !== 'string' || !(PRECHECK_ACTIONS as readonly string[]).includes(action)) throw invalid('action', PRECHECK_ACTIONS.join(', '))
  return action as PrecheckAction
}

const CONSENT_ACTIONS: readonly PrecheckAction[] = ['CONSENT_YES', 'CONSENT_NO']

/** The action table of design 2.3: the first row that applies, as a 409 with its code; null when the action may run. */
export function actionConflict(status: SlipPrecheck['status'], action: PrecheckAction): ConflictCode | null {
  const consent = CONSENT_ACTIONS.includes(action)
  if (status === 'CONFIRMED') return 'already_confirmed'
  if (status === 'SUPERSEDED') return 'superseded'
  if (status === 'AWAITING_CONSENT') return consent ? null : 'consent_pending'
  if (consent) return 'no_consent_question'
  if (status === 'READY') return action === 'CONFIRM' ? null : 'ready_not_team'
  return action === 'SEND_TO_TEAM' ? null : 'not_ready'
}

type Outcome = Omit<PrecheckConfirm, 'precheck_id' | 'status' | 'confirmed_as' | 'consent' | 'doctor_check'>

function claimOutcome(rt: MockRuntime, merchantId: string, before: number): Outcome {
  const claimId = rt.conversation(merchantId).claimId
  const decision = rt.decisions.find((d) => d.claim_id === claimId)
  if (!claimId || !decision) throw new Error('the slip claim was not decided')
  const kase = rt.cases.find((c) => c.kind !== 'DISPUTE' && c.decision?.claim_id === claimId) ?? null
  const messages = rt.messages.slice(before).filter((m: Message) => m.merchant_id === merchantId)
  return { claim_id: claimId, decision_id: decision.id, outcome: decision.outcome, case_id: kase?.id ?? null, messages }
}

function slipFacts(found: StoredPrecheck) {
  return { ...found.read, name_score: found.read.name_score }
}

function store(rt: MockRuntime, merchantId: string, updated: StoredPrecheck): void {
  const mine = prechecksOf(rt, merchantId)
  savePrechecks(rt, merchantId, { ...mine, checks: new Map([...mine.checks, [updated.view.precheck_id, updated]]) })
}

/** CONFIRM: nothing is filed; the doctor question is asked once, in the chat and in the answer. */
function askDoctorQuestion(rt: MockRuntime, merchantId: string, found: StoredPrecheck): RouteResult {
  const id = found.view.precheck_id
  const before = rt.messages.length
  askConsent(rt, merchantId, id, slipFacts(found))
  store(rt, merchantId, { ...found, view: { ...found.view, status: 'AWAITING_CONSENT' } })
  rt.record(`merchant:${merchantId}`, 'precheck.confirmed', 'precheck', id, { merchant_id: merchantId, precheck_id: id, action: 'CONFIRM', awaiting_consent: true, claim_id: null })
  const messages = rt.messages.slice(before).filter((m: Message) => m.merchant_id === merchantId)
  const consent = consentView(id, slipFacts(found), 'ASKED', null)
  return ok({ precheck_id: id, status: 'AWAITING_CONSENT', confirmed_as: 'FIELDS_CONFIRMED', claim_id: null, decision_id: null, outcome: null, case_id: null, messages, consent, doctor_check: null } satisfies PrecheckConfirm)
}

/** CONSENT_YES / CONSENT_NO and SEND_TO_TEAM: record the answer first (consent), then file the claim as the chat does. */
function fileClaim(rt: MockRuntime, merchant: Parameters<typeof submitSlip>[1], found: StoredPrecheck, action: PrecheckAction): RouteResult {
  const id = found.view.precheck_id
  const before = rt.messages.length
  const consentGiven = CONSENT_ACTIONS.includes(action) ? action === 'CONSENT_YES' : null
  if (consentGiven !== null) recordConsent(rt, merchant.id, { consent: consentGiven, precheckId: id })
  // The merchant never edits a value: a confirmed read is filed as read, SEND_TO_TEAM files the empty read (referred).
  const doctor = consentGiven === null ? undefined : { consent: consentGiven, precheckId: id }
  submitSlip(rt, merchant, found.mediaUrl, action === 'SEND_TO_TEAM' ? null : found.sample, doctor)
  const outcome = claimOutcome(rt, merchant.id, before)
  const consent: DoctorConsent | null = consentGiven === null ? null : consentView(id, slipFacts(found), consentGiven ? 'GIVEN' : 'REFUSED', rt.nowIso)
  store(rt, merchant.id, { ...found, confirmed: true, view: { ...found.view, status: 'CONFIRMED' }, ...(consentGiven === null ? {} : { consent: { granted: consentGiven, at: rt.nowIso } }) })
  rt.record(`merchant:${merchant.id}`, 'precheck.confirmed', 'precheck', id, { merchant_id: merchant.id, precheck_id: id, action, claim_id: outcome.claim_id })
  const confirmedAs = action === 'SEND_TO_TEAM' ? 'SENT_TO_TEAM' : 'FIELDS_CONFIRMED'
  return ok({ precheck_id: id, status: 'CONFIRMED', confirmed_as: confirmedAs, ...outcome, consent, doctor_check: null } satisfies PrecheckConfirm)
}

function confirmPrecheck(ctx: RouteContext): RouteResult {
  requireFlag()
  const merchant = merchantParam(ctx)
  const rt = ctx.backend.runtime
  const action = actionOf(ctx)
  const found = PRECHECK_ID.test(ctx.params[1]) ? prechecksOf(rt, merchant.id).checks.get(ctx.params[1]) : undefined
  if (!found) throw notFound(`pre-check ${ctx.params[1]}`)
  const code = actionConflict(found.view.status, action)
  if (code !== null) throw conflict(code, `${action} is not possible on a ${found.view.status} pre-check`)
  const conv = rt.conversation(merchant.id)
  if (!conv.checkinSent || conv.claimId !== null) throw conflict('no_checkin', 'the claim was already filed')
  return action === 'CONFIRM' ? askDoctorQuestion(rt, merchant.id, found) : fileClaim(rt, merchant, found, action)
}

const OPEN_STATUSES: readonly SlipPrecheck['status'][] = ['READY', 'RETAKE', 'NEEDS_TEAM']

function openPrecheck(ctx: RouteContext): RouteResult {
  requireFlag()
  const merchant = merchantParam(ctx)
  const rt = ctx.backend.runtime
  const conv = rt.conversation(merchant.id)
  const open = conv.checkinSent && conv.claimId === null
  const latest = open ? [...prechecksOf(rt, merchant.id).checks.values()].at(-1) ?? null : null
  const waiting = latest?.view.status === 'AWAITING_CONSENT' ? consentView(latest.view.precheck_id, slipFacts(latest), 'ASKED', null) : null
  const body: PrecheckOpen = {
    merchant_id: merchant.id,
    checkin_open: open,
    first_silent_day: open ? addDays(rt.scenario.day, -1) : null,
    precheck: latest && OPEN_STATUSES.includes(latest.view.status) ? latest.view : null,
    awaiting_consent: waiting,
  }
  return ok(body)
}

export const PRECHECK_ROUTES: readonly Route[] = [
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/slip-precheck$/, handler: postPrecheck },
  { method: 'GET', pattern: /^\/api\/merchants\/(S-\d{4})\/slip-precheck\/open$/, handler: openPrecheck },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/slip-precheck\/(PC-\d+)\/confirm$/, handler: confirmPrecheck },
]
