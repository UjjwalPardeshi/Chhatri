/**
 * Mock POST /api/merchants/{id}/ask, POST /api/voice/stt and POST /api/voice/tts (data-model 5.2 and 5.11). Behind the
 * flags `n2_ask_chhatri` and `n4_voice` like the backend (404 `not_found` while one is off). Every answer is a
 * recorded sample, so its label is SIMULATED, provider `mock`, reason `MOCK_BACKEND` (data-model 6, ADR 0004). The
 * intents are the word lists of the built service; the sentences are the deck's and the engine's own explanation, and
 * the numbers come from the merchant's records, never from this file. A voice question must carry the ids of the
 * chips for every amount and date in its final text, or the answer is 409 `mentions_unconfirmed`.
 */
import type { Source } from '../api/types'
import { isFeatureEnabled } from '../features'
import { ta } from '../miniapp/copy/ask'
import { t } from '../miniapp/lib/copy'
import { formatInr } from '../lib/money'
import type { AskClause, AskFact, AskIntent, NextActionKind } from '../miniapp/api/ask'
import { MockHttpError } from './backend'
import { openOrFindDispute } from './cases'
import { MSG } from './catalogue'
import { findMentions } from './askMentions'
import { coverStatusText, deriveCover, storedCover } from './endpoints/cover'
import { moneyFacts } from './endpoints/provenance'
import { POLICY_RULES } from './fixtures'
import { bodyField, invalid, merchantById, notFound, ok, type Route, type RouteContext, type RouteResult } from './http'
import { VOICE_DEMOS } from './conversation'
import type { MockRuntime } from './runtime'

const ASK_FLAG = 'n2_ask_chhatri'
const VOICE_FLAG = 'n4_voice'
const MAX_QUESTION = 500
const MAX_AUDIO_BYTES = 5 * 1024 * 1024
const SCAM = /otp|\bpin\b|password|पासवर्ड|install|इंस्टॉल|फ़ीस|\bfee\b|remote|anydesk/i
const MOCK_LABEL = { mode: 'SIMULATED', provider: 'mock', model: null, fallback_reason: 'MOCK_BACKEND', attempts: [] } as const

type Remembered = { asks: Map<string, { merchantId: string }>; stts: Map<string, { merchantId: string }> }
const MEMORY = new WeakMap<MockRuntime, Remembered>()

function memory(rt: MockRuntime): Remembered {
  const known = MEMORY.get(rt)
  if (known) return known
  const fresh: Remembered = { asks: new Map(), stts: new Map() }
  MEMORY.set(rt, fresh)
  return fresh
}

const serial = (prefix: string, n: number): string => `${prefix}-${String(n).padStart(6, '0')}`

function requireFlag(flag: 'n2_ask_chhatri' | 'n4_voice'): void {
  if (!isFeatureEnabled(flag)) throw notFound('route')
}

type Lines = { hi: string; en: string }
type Draft = { intent: AskIntent; lines: Lines; clauses: AskClause[]; facts: AskFact[]; next: NextActionKind; handoff?: boolean; caseId?: string }

const rulesSource = (ref: string, label: string, clause: string): Source => ({ kind: 'RULES', label, ref: `rules:${POLICY_RULES.version}:${ref}`, as_of: null, origin: 'CONFIG', clause })
const fact = (key: string, en: string, hi: string, value: string, source: Source): AskFact => ({ key, label_en: en, label_hi: hi, value, sources: [source] })
const both = (key: Parameters<typeof t>[0], params: Record<string, string | number> = {}): Lines => ({ hi: t(key, 'hi', params), en: t(key, 'en', params) })
const fixed = (key: Parameters<typeof ta>[0]): Lines => ({ hi: ta(key, 'hi'), en: ta(key, 'en') })

const latestPaid = (rt: MockRuntime, merchantId: string) => {
  const paid = new Set(rt.payouts.filter((p) => p.merchant_id === merchantId && p.status === 'CREDITED').map((p) => p.decision_id))
  return rt.decisions.toReversed().find((d) => paid.has(d.id)) ?? null
}

function whyAmount(rt: MockRuntime, merchantId: string): Draft {
  const decision = latestPaid(rt, merchantId)
  const ex = decision?.explanation
  if (!decision || !ex) return help('WHY_AMOUNT')
  const facts = moneyFacts({ rt, merchant: merchantById(merchantId), decision }).map((f): AskFact => ({ ...f, label_hi: f.label_en }))
  return { intent: 'WHY_AMOUNT', lines: { hi: ex.formula_hi, en: ex.formula_en }, clauses: [{ id: 'C4.1', title: 'Payout formula' }], facts, next: 'SEE_CLAIM' }
}

function help(intent: AskIntent): Draft {
  return { intent, lines: fixed('FALLBACK_HELP'), clauses: [], facts: [], next: 'ASK_AGAIN' }
}

function handoff(): Draft {
  return { intent: 'UNKNOWN', lines: fixed('ASK_HANDOFF'), clauses: [], facts: [], next: 'TALK_TO_TEAM', handoff: true }
}

function dispute(rt: MockRuntime, merchantId: string, question: string): Draft {
  const decision = latestPaid(rt, merchantId)
  if (!decision) return help('DISPUTE_AMOUNT')
  const { opened, already } = openOrFindDispute(rt, merchantById(merchantId), question, decision)
  const ack = already ? MSG.disputeAlreadyOpen(opened.id) : MSG.disputeAck
  return { intent: 'DISPUTE_AMOUNT', lines: { hi: `${ack.hi}\n${MSG.caseChip(opened.id).hi ?? MSG.caseChip(opened.id).en}`, en: `${ack.en}\n${MSG.caseChip(opened.id).en}` }, clauses: [{ id: 'C9', title: 'Disputes' }], facts: [], next: 'TRACK_CASE', caseId: opened.id }
}

function coverStatus(rt: MockRuntime, merchantId: string): Draft {
  const stored = storedCover(rt, merchantId)
  const { status, premium_due } = deriveCover(stored, rt.scenario.day)
  const text = coverStatusText(status, premium_due, stored)
  const source: Source = { kind: 'COVER', label: 'Cover record', ref: `cover:${merchantId}`, as_of: rt.nowIso, origin: 'SIMULATED', clause: 'C5' }
  return { intent: 'COVER_STATUS', lines: text, clauses: [{ id: 'C5', title: 'When cover starts' }], facts: [fact('cover.status', 'Cover status', 'कवर की स्थिति', status, source)], next: status === 'NONE' ? 'GET_COVER' : 'SEE_COVER' }
}

/** Questions the word lists do not know: a model answers them in the real service, here a recorded sample from the deck. */
function clauseAnswer(question: string): Draft | null {
  const waiting = POLICY_RULES.cover.waiting_period_days
  const limit = formatInr(POLICY_RULES.annual_limit_rupees * 100)
  if (/waiting|वेटिंग/i.test(question)) {
    return { intent: 'UNKNOWN', lines: both('jargon.waiting_period.what', { waiting_days: waiting }), clauses: [{ id: 'C5', title: 'Waiting period' }], facts: [fact('rules.waiting_days', 'Waiting period', 'वेटिंग पीरियड', `${waiting}`, rulesSource('waiting_period_days', 'Policy rules', 'C5'))], next: 'SEE_COVER' }
  }
  if (/limit|सीमा/i.test(question)) {
    return { intent: 'UNKNOWN', lines: both('jargon.annual_limit.what', { window_days: 365, annual_limit: limit }), clauses: [{ id: 'C4.3', title: 'Annual limit' }], facts: [fact('rules.annual_limit', 'Yearly limit', 'साल की सीमा', limit, rulesSource('annual_limit_rupees', 'Policy rules', 'C4.3'))], next: 'SEE_COVER' }
  }
  if (/what is covered|क्या कवर है|covered/i.test(question)) {
    return { intent: 'UNKNOWN', lines: both('explain.c2.body', {}), clauses: [{ id: 'C2', title: 'Rain and lost sales' }, { id: 'C3', title: 'Hospital cash' }], facts: [], next: 'SEE_COVER' }
  }
  if (/question.*payout|सवाल कैसे|कैसे उठाऊँ/i.test(question)) {
    return { intent: 'UNKNOWN', lines: both('help.dispute.hint'), clauses: [{ id: 'C9', title: 'Questions and complaints' }], facts: [], next: 'TALK_TO_TEAM' }
  }
  return null
}

function draftFor(rt: MockRuntime, merchantId: string, question: string): Draft {
  if (/क्यों|\bwhy\b/i.test(question)) return whyAmount(rt, merchantId)
  if (/ज़्यादा|ज्यादा|नुकसान|\bbigger\b/i.test(question)) return dispute(rt, merchantId, question)
  const clause = clauseAnswer(question)
  if (clause) return clause
  if (/अस्पताल|बुखार|hospital|fever/i.test(question)) {
    return rt.conversation(merchantId).checkinSent ? { intent: 'REPORT_ILLNESS', lines: { hi: MSG.askSlip.hi ?? MSG.askSlip.en, en: MSG.askSlip.en }, clauses: [], facts: [], next: 'SEND_SLIP' } : help('REPORT_ILLNESS')
  }
  if (/cover|कवर|start|शुरू/i.test(question)) return coverStatus(rt, merchantId)
  if (/^\s*(hi|hello|namaste|नमस्ते)\b/i.test(question)) return help('GREETING')
  return handoff()
}

function scamLines(draft: Draft): Draft {
  return { ...draft, lines: fixed('ASK_SCAM_WARNING'), next: 'ASK_AGAIN', handoff: false }
}

function validQuestion(body: unknown): string {
  const question = bodyField(body, 'question')
  if (typeof question !== 'string' || question.trim().length === 0) throw invalid('question', 'must not be empty')
  if (question.trim().length > MAX_QUESTION) throw invalid('question', `at most ${MAX_QUESTION} characters`)
  return question.trim()
}

/** The ids of the chips the final text needs, against the ids the merchant confirmed. */
function checkMentions(rt: MockRuntime, ctx: RouteContext, merchantId: string, question: string): void {
  const sttId = bodyField(ctx.body, 'stt_id')
  if (sttId === undefined) return
  const known = typeof sttId === 'string' ? memory(rt).stts.get(sttId) : undefined
  if (!known || known.merchantId !== merchantId) throw notFound(`transcript ${String(sttId)}`)
  const confirmed = bodyField(ctx.body, 'confirmed_mentions')
  const done = new Set(Array.isArray(confirmed) ? confirmed.filter((c): c is string => typeof c === 'string') : [])
  const missing = findMentions(question, Number(rt.scenario.day.slice(0, 4))).filter((m) => !done.has(m.id))
  if (missing.length > 0) throw new MockHttpError('mentions_unconfirmed', 'confirm each amount and date first', 409, { mentions: missing.map((m) => m.id).join(',') })
}

function postAsk(ctx: RouteContext): RouteResult {
  requireFlag(ASK_FLAG)
  const merchant = merchantById(ctx.params[0])
  const question = validQuestion(ctx.body)
  const lang = bodyField(ctx.body, 'lang') ?? 'hi'
  if (lang !== 'hi' && lang !== 'en') throw invalid('lang', 'hi or en')
  const rt = ctx.backend.runtime
  checkMentions(rt, ctx, merchant.id, question)
  const scam = SCAM.test(question)
  const base = draftFor(rt, merchant.id, question)
  const draft = scam ? scamLines(base) : base
  const remembered = memory(rt)
  const askId = serial('AQ', remembered.asks.size + 1)
  remembered.asks.set(askId, { merchantId: merchant.id })
  rt.record('ai-agent', 'ask.answered', 'merchant', merchant.id, { ask_id: askId, intent: draft.intent, clauses: draft.clauses.map((c) => c.id), scam })
  return ok({
    ask_id: askId,
    intent: draft.intent,
    intent_source: 'rules',
    lang,
    answer: lang === 'hi' ? draft.lines.hi : draft.lines.en,
    answer_en: draft.lines.en,
    clauses: draft.clauses,
    facts_used: draft.facts,
    next_action: { kind: draft.next, label_hi: ta(`next_action.${draft.next}`, 'hi'), label_en: ta(`next_action.${draft.next}`, 'en') },
    handoff: draft.handoff ?? false,
    case_id: draft.caseId ?? null,
    scam_warning: scam,
    ...MOCK_LABEL,
  })
}

/** Magic-byte sniffing of the audio types the real route accepts: OGG, WebM, MP3, WAV and M4A. */
export function sniffAudio(bytes: Uint8Array): string | null {
  const ascii = (from: number, to: number): string => String.fromCharCode(...bytes.slice(from, to))
  if (ascii(0, 4) === 'OggS') return 'audio/ogg'
  if (bytes[0] === 0x1a && bytes[1] === 0x45 && bytes[2] === 0xdf && bytes[3] === 0xa3) return 'audio/webm'
  if (ascii(0, 3) === 'ID3' || (bytes[0] === 0xff && (bytes[1] & 0xe0) === 0xe0)) return 'audio/mpeg'
  if (ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WAVE') return 'audio/wav'
  if (ascii(4, 8) === 'ftyp') return 'audio/mp4'
  return null
}

async function transcriptOf(ctx: RouteContext, rt: MockRuntime): Promise<{ transcript: string; code: string; provider: 'browser' | 'mock'; seconds: number | null }> {
  if (!ctx.form) {
    const transcript = bodyField(ctx.body, 'transcript')
    if (typeof transcript !== 'string' || transcript.trim().length === 0) throw invalid('transcript', 'must not be empty')
    if (bodyField(ctx.body, 'source') !== 'browser') throw invalid('source', 'must be browser')
    const code = bodyField(ctx.body, 'language_code')
    return { transcript: transcript.trim(), code: typeof code === 'string' ? code : 'unknown', provider: 'browser', seconds: null }
  }
  const file = ctx.form.get('file')
  if (!(file instanceof Blob)) throw invalid('file', 'attach a recording')
  if (file.size === 0) throw invalid('file', 'recording is empty')
  if (file.size > MAX_AUDIO_BYTES) throw new MockHttpError('payload_too_large', 'recording must be 5 MB or smaller', 413)
  if (!sniffAudio(new Uint8Array(await file.slice(0, 16).arrayBuffer()))) throw new MockHttpError('unsupported_media_type', 'recording must be OGG, WebM, MP3, WAV or M4A', 415)
  const byScenario: Record<string, keyof typeof VOICE_DEMOS> = { monsoon: 'why', illness: 'ill', illness_mismatch: 'ill', buy_cover: 'cover' }
  const demo = VOICE_DEMOS[byScenario[rt.scenario.name] ?? 'why']
  return { transcript: demo.hi, code: 'hi-IN', provider: 'mock', seconds: demo.seconds }
}

async function postStt(ctx: RouteContext): Promise<RouteResult> {
  requireFlag(VOICE_FLAG)
  const merchantId = ctx.form ? ctx.form.get('merchant_id') : bodyField(ctx.body, 'merchant_id')
  if (typeof merchantId !== 'string' || !/^S-\d{4}$/.test(merchantId)) throw invalid('merchant_id', 'must look like S-0142')
  const merchant = merchantById(merchantId)
  const rt = ctx.backend.runtime
  const heard = await transcriptOf(ctx, rt)
  const remembered = memory(rt)
  const sttId = serial('ST', remembered.stts.size + 1)
  remembered.stts.set(sttId, { merchantId: merchant.id })
  return ok({
    stt_id: sttId,
    transcript: heard.transcript,
    language_code: heard.code,
    language_probability: null,
    duration_s: heard.seconds,
    mentions: findMentions(heard.transcript, Number(rt.scenario.day.slice(0, 4))),
    ...MOCK_LABEL,
    provider: heard.provider,
  })
}

function postTts(ctx: RouteContext): RouteResult {
  requireFlag(VOICE_FLAG)
  const merchant = merchantById(String(bodyField(ctx.body, 'merchant_id') ?? ''))
  const askId = bodyField(ctx.body, 'ask_id')
  const known = typeof askId === 'string' ? memory(ctx.backend.runtime).asks.get(askId) : undefined
  if (!known || known.merchantId !== merchant.id) throw notFound(`ask ${String(askId)}`)
  const lang = bodyField(ctx.body, 'lang')
  if (lang !== 'hi' && lang !== 'en') throw invalid('lang', 'hi or en')
  return ok({ audio_url: null, mime_type: null, mode: 'SIMULATED', provider: 'browser', model: null, fallback_reason: 'MOCK_BACKEND' })
}

export const ASK_ROUTES: readonly Route[] = [
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/ask$/, handler: postAsk },
  { method: 'POST', pattern: /^\/api\/voice\/stt$/, handler: postStt },
  { method: 'POST', pattern: /^\/api\/voice\/tts$/, handler: postTts },
]
