/**
 * Types and parsers of Ask Chhatri and voice (data-model 5.2 and 5.11, fs-05 sections 10 to 12). Every parser takes
 * `unknown` and returns a new typed value. Enums are strict (a mode, provider, intent or next action outside its
 * closed list is a `ContractViolation`) and a fact without a source is refused; fields this app does not read are
 * ignored, so a backend that adds one does not break the screen.
 */
import { SOURCE_KINDS, type Source } from '../../api/types'
import { ContractViolation } from './parse'

type Json = Readonly<Record<string, unknown>>

export const ASK_INTENTS = ['WHY_AMOUNT', 'DISPUTE_AMOUNT', 'REPORT_ILLNESS', 'BUY_COVER', 'COVER_STATUS', 'GREETING', 'AFFIRM', 'DENY', 'UNKNOWN'] as const
export const NEXT_ACTION_KINDS = ['SEE_CLAIM', 'SEE_COVER', 'GET_COVER', 'SEND_SLIP', 'TRACK_CASE', 'OPEN_CONSENTS', 'TALK_TO_TEAM', 'ASK_AGAIN'] as const
export const AI_MODES = ['LIVE', 'SIMULATED', 'FALLBACK'] as const
export const AI_PROVIDERS = ['rules', 'gemini', 'sarvam', 'template', 'simulated', 'mock', 'browser', 'none'] as const
export const MENTION_KINDS = ['amount', 'date'] as const
export const FALLBACK_REASONS = [
  'NO_KEY', 'MODEL_NOT_SET', 'MOCK_BACKEND', 'FREE_TIER_BLOCKED', 'TIMEOUT', 'RATE_LIMITED', 'PROVIDER_ERROR', 'INVALID_REPLY',
  'GUARD_BLOCKED', 'INJECTION_SUSPECTED', 'FORCED',
] as const

export const ASK_MAX_CHARS = 500
export const VOICE_MAX_SECONDS = 30

export type AskIntent = (typeof ASK_INTENTS)[number]
export type NextActionKind = (typeof NEXT_ACTION_KINDS)[number]
export type AiMode = (typeof AI_MODES)[number]
export type AiProvider = (typeof AI_PROVIDERS)[number]
export type MentionKind = (typeof MENTION_KINDS)[number]

/** The H26 label every AI-backed answer carries. */
export type AiLabel = {
  mode: AiMode
  provider: AiProvider
  model: string | null
  fallback_reason: string | null
}
export type AiAttempt = { provider: string; outcome: string; ms: number }

export type AskClause = { id: string; title: string }
export type AskFact = { key: string; label_hi: string; label_en: string; value: string; sources: Source[] }
export type AskNextAction = { kind: NextActionKind; label_hi: string; label_en: string }

export type AskAnswer = AiLabel & {
  ask_id: string
  intent: AskIntent
  lang: 'hi' | 'en'
  answer: string
  answer_en: string
  clauses: AskClause[]
  facts_used: AskFact[]
  next_action: AskNextAction
  handoff: boolean
  case_id: string | null
  scam_warning: boolean
  attempts: AiAttempt[]
}

export type Mention = {
  id: string
  kind: MentionKind
  heard: string
  value: string | null
  value_paise: number | null
  value_date: string | null
  chip_hi: string
  chip_en: string
}

export type SttResult = AiLabel & {
  stt_id: string
  transcript: string
  language_code: string
  duration_s: number | null
  mentions: Mention[]
  attempts: AiAttempt[]
}

export type TtsResult = AiLabel & { audio_url: string | null; mime_type: string | null }

export type AskRequest = { question: string; lang: 'hi' | 'en'; stt_id?: string; confirmed_mentions?: string[] }
export type SttRequest =
  | { merchant_id: string; transcript: string; source: 'browser'; language_code: string }
  | { merchant_id: string; file: Blob; filename: string; lang_hint?: 'hi-IN' | 'en-IN' | 'unknown' }

const ASK_ID = /^AQ-\d{6}$/
const STT_ID = /^ST-\d{6}$/
const CLAUSE_ID = /^C(?:[1-9]|1[0-2])(?:\.[1-4])?$/
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const ORIGINS = ['LIVE', 'SIMULATED', 'CONFIG'] as const

const fail = (path: string, reason: string): never => {
  throw new ContractViolation(`${path}: ${reason}`)
}

function record(value: unknown, path: string): Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Json) : fail(path, 'expected an object')
}

function list(value: unknown, path: string): readonly unknown[] {
  return Array.isArray(value) ? value : fail(path, 'expected a list')
}

function text(r: Json, key: string, path: string): string {
  const value = r[key]
  return typeof value === 'string' ? value : fail(`${path}.${key}`, 'expected a string')
}

function textOrNull(r: Json, key: string, path: string): string | null {
  return r[key] === null || r[key] === undefined ? null : text(r, key, path)
}

function bool(r: Json, key: string, path: string): boolean {
  const value = r[key]
  return typeof value === 'boolean' ? value : fail(`${path}.${key}`, 'expected true or false')
}

function numberOrNull(r: Json, key: string, path: string): number | null {
  const value = r[key]
  if (value === null || value === undefined) return null
  return typeof value === 'number' && Number.isFinite(value) ? value : fail(`${path}.${key}`, 'expected a number')
}

function oneOf<T extends string>(r: Json, key: string, path: string, allowed: readonly T[]): T {
  const value = r[key]
  return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? (value as T) : fail(`${path}.${key}`, `expected one of ${allowed.join(', ')}`)
}

function matching(r: Json, key: string, path: string, pattern: RegExp, hint: string): string {
  const value = text(r, key, path)
  return pattern.test(value) ? value : fail(`${path}.${key}`, `expected ${hint}`)
}

function parseLabel(r: Json, path: string): AiLabel {
  const mode = oneOf(r, 'mode', path, AI_MODES)
  const provider = oneOf(r, 'provider', path, AI_PROVIDERS)
  const reason = textOrNull(r, 'fallback_reason', path)
  if (mode !== 'LIVE' && reason === null) return fail(`${path}.fallback_reason`, `a ${mode} label needs a reason`)
  return { mode, provider, model: textOrNull(r, 'model', path), fallback_reason: reason }
}

function parseAttempts(raw: unknown, path: string): AiAttempt[] {
  if (raw === undefined) return []
  return list(raw, path).map((item, i) => {
    const r = record(item, `${path}[${i}]`)
    return { provider: text(r, 'provider', `${path}[${i}]`), outcome: text(r, 'outcome', `${path}[${i}]`), ms: numberOrNull(r, 'ms', `${path}[${i}]`) ?? 0 }
  })
}

function parseSource(raw: unknown, path: string): Source {
  const r = record(raw, path)
  return {
    kind: oneOf(r, 'kind', path, SOURCE_KINDS),
    label: text(r, 'label', path),
    ref: text(r, 'ref', path),
    as_of: textOrNull(r, 'as_of', path),
    origin: oneOf(r, 'origin', path, ORIGINS),
    clause: textOrNull(r, 'clause', path),
  }
}

function parseFact(raw: unknown, path: string): AskFact {
  const r = record(raw, path)
  const sources = list(r.sources, `${path}.sources`).map((s, i) => parseSource(s, `${path}.sources[${i}]`))
  if (sources.length === 0) return fail(`${path}.sources`, 'a fact needs at least one source')
  return { key: text(r, 'key', path), label_hi: text(r, 'label_hi', path), label_en: text(r, 'label_en', path), value: text(r, 'value', path), sources }
}

function parseClause(raw: unknown, path: string): AskClause {
  const r = record(raw, path)
  return { id: matching(r, 'id', path, CLAUSE_ID, 'a clause id such as C4.1'), title: text(r, 'title', path) }
}

/** POST /api/merchants/{id}/ask. */
export function parseAskAnswer(raw: unknown): AskAnswer {
  const path = 'ask'
  const r = record(raw, path)
  const next = record(r.next_action, `${path}.next_action`)
  const lang = oneOf(r, 'lang', path, ['hi', 'en'] as const)
  return {
    ...parseLabel(r, path),
    ask_id: matching(r, 'ask_id', path, ASK_ID, 'an id like AQ-000001'),
    intent: oneOf(r, 'intent', path, ASK_INTENTS),
    lang,
    answer: text(r, 'answer', path),
    answer_en: text(r, 'answer_en', path),
    clauses: list(r.clauses, `${path}.clauses`).map((c, i) => parseClause(c, `${path}.clauses[${i}]`)),
    facts_used: list(r.facts_used, `${path}.facts_used`).map((f, i) => parseFact(f, `${path}.facts_used[${i}]`)),
    next_action: {
      kind: oneOf(next, 'kind', `${path}.next_action`, NEXT_ACTION_KINDS),
      label_hi: text(next, 'label_hi', `${path}.next_action`),
      label_en: text(next, 'label_en', `${path}.next_action`),
    },
    handoff: bool(r, 'handoff', path),
    case_id: textOrNull(r, 'case_id', path),
    scam_warning: bool(r, 'scam_warning', path),
    attempts: parseAttempts(r.attempts, `${path}.attempts`),
  }
}

function parseMention(raw: unknown, path: string): Mention {
  const r = record(raw, path)
  const kind = oneOf(r, 'kind', path, MENTION_KINDS)
  const value = textOrNull(r, 'value', path)
  const paise = numberOrNull(r, 'value_paise', path)
  const date = textOrNull(r, 'value_date', path)
  if (paise !== null && !Number.isInteger(paise)) return fail(`${path}.value_paise`, 'expected whole paise')
  if (date !== null && !ISO_DATE.test(date)) return fail(`${path}.value_date`, 'expected a date like 2025-08-19')
  if (value === null && (paise !== null || date !== null)) return fail(`${path}.value`, 'a value is needed when paise or a date is set')
  return { id: text(r, 'id', path), kind, heard: text(r, 'heard', path), value, value_paise: paise, value_date: date, chip_hi: text(r, 'chip_hi', path), chip_en: text(r, 'chip_en', path) }
}

/** POST /api/voice/stt. */
export function parseStt(raw: unknown): SttResult {
  const path = 'stt'
  const r = record(raw, path)
  const mentions = list(r.mentions, `${path}.mentions`).map((m, i) => parseMention(m, `${path}.mentions[${i}]`))
  if (new Set(mentions.map((m) => m.id)).size !== mentions.length) return fail(`${path}.mentions`, 'ids must be unique')
  return {
    ...parseLabel(r, path),
    stt_id: matching(r, 'stt_id', path, STT_ID, 'an id like ST-000001'),
    transcript: text(r, 'transcript', path),
    language_code: text(r, 'language_code', path),
    duration_s: numberOrNull(r, 'duration_s', path),
    mentions,
    attempts: parseAttempts(r.attempts, `${path}.attempts`),
  }
}

/** POST /api/voice/tts. A null `audio_url` means the client speaks the text itself. */
export function parseTts(raw: unknown): TtsResult {
  const path = 'tts'
  const r = record(raw, path)
  const audio = textOrNull(r, 'audio_url', path)
  const mime = textOrNull(r, 'mime_type', path)
  if (audio !== null && !audio.startsWith('/api/media/')) return fail(`${path}.audio_url`, 'expected /api/media/{id} or null')
  if (audio !== null && mime === null) return fail(`${path}.mime_type`, 'needed with audio_url')
  return { ...parseLabel(r, path), audio_url: audio, mime_type: mime }
}
