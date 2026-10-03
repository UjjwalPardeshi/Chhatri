/**
 * Strict parsers for the slip pre-check routes (data-model 5.3, fs-02 section 7.3). Same stance as `parse.ts`: an unknown
 * field, a value outside its enum or an impossible combination raises `ContractViolation`. Beyond the shape, the parser
 * holds the invariants the screen relies on: six slots in a fixed order whose state agrees with the value, values that
 * are plain text, a READY check with no reason, a RETAKE or NEEDS_TEAM check with both a reason and a guidance line, the
 * one button each status allows, and an honest label (a SIMULATED answer never names a live provider). The confirm and
 * open answers (design 2.4) hold theirs too: AWAITING_CONSENT files nothing and asks the doctor question, CONFIRMED
 * names the claim, and only a claim whose doctor is still being asked may be REFERRED without a case.
 */
import {
  DOCTOR_CONSENT_PURPOSE,
  DOCTOR_CONSENT_STATUSES,
  PRECHECK_ACTION_KINDS,
  PRECHECK_GUIDANCE_KEYS,
  PRECHECK_REASONS,
  PRECHECK_STATUSES,
  SLIP_CHECKLIST_IDS,
  SLIP_SLOT_KEYS,
  type DoctorCheck,
  type DoctorConsent,
  type PrecheckAttempt,
  type PrecheckConfirm,
  type PrecheckOpen,
  type SlipChecklistLine,
  type SlipPrecheck,
  type SlipSlot,
  type Source,
} from '../../api/types'
import { ContractViolation, parseSource } from './parse'

type Json = Readonly<Record<string, unknown>>

const PRECHECK_ID = /^PC-\d{6}$/
const MEDIA_ID = /^MD-\d{6,}$/
const MERCHANT_ID = /^S-\d{4}$/
const CLAIM_ID = /^CL-\d{6,}$/
const DECISION_ID = /^D-\d{6,}$/
const CASE_ID = /^C-\d+$/
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/
/** fs-02 7.3.7: letters of any script, digits, spaces and . , - ' / ( ) & only. */
const PLAIN_TEXT = /^[\p{L}\p{M}\p{N} .,\-'/()&]+$/u
const DOCUMENT_TYPES = ['admission_slip', 'discharge_summary', 'prescription', 'bill', 'other'] as const
const MODES = ['LIVE', 'SIMULATED', 'FALLBACK'] as const
const PROVIDERS = ['gemini', 'sarvam', 'simulated', 'mock', 'none'] as const
const OUTCOMES = ['APPROVED', 'REFERRED', 'DECLINED'] as const
const NOTE_KEY = /^SLIP_NOTE_[A-Z_]+$/
const REQUIRED_SLOTS: readonly string[] = ['patient_name', 'admission_date']
const MAX_LENGTH: Readonly<Record<string, number>> = { patient_name: 80, hospital_name: 120, doctor_name: 80, doctor_registration_no: 32 }
export const MAX_PHOTOS = 3

function fail(path: string, problem: string): never {
  throw new ContractViolation(`${path}: ${problem}`)
}

function object(value: unknown, path: string, keys: readonly string[]): Json {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'expected an object')
  const record = value as Json
  const unknown = Object.keys(record).filter((key) => !keys.includes(key))
  if (unknown.length > 0) fail(path, `unknown field ${unknown.join(', ')}`)
  const missing = keys.filter((key) => !(key in record))
  if (missing.length > 0) fail(path, `missing field ${missing.join(', ')}`)
  return record
}

const at = (path: string, key: string): string => `${path}.${key}`

function text(record: Json, key: string, path: string): string {
  const value = record[key]
  return typeof value === 'string' ? value : fail(at(path, key), 'expected text')
}

function textOrNull(record: Json, key: string, path: string): string | null {
  return record[key] === null ? null : text(record, key, path)
}

function whole(record: Json, key: string, path: string, min: number, max: number): number {
  const value = record[key]
  return typeof value === 'number' && Number.isInteger(value) && value >= min && value <= max ? value : fail(at(path, key), `expected a whole number from ${min} to ${max}`)
}

function oneOf<T extends string>(record: Json, key: string, path: string, allowed: readonly T[]): T {
  const value = record[key]
  return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? (value as T) : fail(at(path, key), `expected one of ${allowed.join(', ')}`)
}

function matching(record: Json, key: string, path: string, pattern: RegExp, hint: string): string {
  const value = text(record, key, path)
  return pattern.test(value) ? value : fail(at(path, key), `expected ${hint}`)
}

function array(value: unknown, path: string): readonly unknown[] {
  return Array.isArray(value) ? value : fail(path, 'expected a list')
}

function slotValue(key: string, value: string, path: string): string {
  if (key === 'admission_date' || key === 'discharge_date') return ISO_DATE.test(value) ? value : fail(path, 'expected a date like 2025-08-20')
  if (!PLAIN_TEXT.test(value)) return fail(path, 'expected plain text (letters, digits, spaces and . , - \' / ( ) &)')
  return value.length <= (MAX_LENGTH[key] ?? 120) ? value : fail(path, 'too long')
}

function parseSlot(raw: unknown, index: number): SlipSlot {
  const path = `slots[${index}]`
  const r = object(raw, path, ['key', 'value', 'state', 'note'])
  const key = oneOf(r, 'key', path, SLIP_SLOT_KEYS)
  if (key !== SLIP_SLOT_KEYS[index]) fail(at(path, 'key'), `expected ${SLIP_SLOT_KEYS[index]} in this position`)
  const empty = REQUIRED_SLOTS.includes(key) ? 'MISSING' : 'NOT_ON_SLIP'
  const state = oneOf(r, 'state', path, ['READ', empty] as const)
  const value = textOrNull(r, 'value', path)
  if (state === 'READ' && (value === null || value === '')) fail(at(path, 'value'), 'a READ slot needs its value')
  if (state !== 'READ' && value !== null) fail(at(path, 'value'), `a ${state} slot has no value`)
  const note = textOrNull(r, 'note', path)
  if (note !== null && !NOTE_KEY.test(note)) fail(at(path, 'note'), 'expected a catalogue key such as SLIP_NOTE_NAME_NOT_LATIN')
  return { key, value: value === null ? null : slotValue(key, value, at(path, 'value')), state, note }
}

function parseSlots(raw: unknown): SlipSlot[] {
  const items = array(raw, 'slots')
  if (items.length !== SLIP_SLOT_KEYS.length) fail('slots', 'expected six slots')
  return items.map((item, index) => parseSlot(item, index))
}

function parseChecklist(raw: unknown): SlipChecklistLine[] {
  const items = array(raw, 'checklist')
  if (items.length !== SLIP_CHECKLIST_IDS.length) fail('checklist', 'expected three lines')
  return items.map((item, index) => {
    const path = `checklist[${index}]`
    const r = object(item, path, ['id', 'state'])
    const id = oneOf(r, 'id', path, SLIP_CHECKLIST_IDS)
    if (id !== SLIP_CHECKLIST_IDS[index]) fail(at(path, 'id'), `expected ${SLIP_CHECKLIST_IDS[index]} in this position`)
    return { id, state: oneOf(r, 'state', path, ['PASS', 'WARN'] as const) }
  })
}

function parseAttempts(raw: unknown): PrecheckAttempt[] {
  return array(raw, 'attempts').map((item, index) => {
    const path = `attempts[${index}]`
    const r = object(item, path, ['provider', 'outcome', 'ms'])
    return { provider: text(r, 'provider', path), outcome: text(r, 'outcome', path), ms: whole(r, 'ms', path, 0, 600_000) }
  })
}

function parseGate(raw: unknown): SlipPrecheck['gate'] {
  const r = object(raw, 'gate', ['passed', 'confidence', 'minimum'])
  const unit = (key: string): number => {
    const value = r[key]
    return typeof value === 'number' && value >= 0 && value <= 1 ? value : fail(at('gate', key), 'expected a number from 0 to 1')
  }
  if (typeof r.passed !== 'boolean') fail('gate.passed', 'expected true or false')
  return { passed: r.passed, confidence: unit('confidence'), minimum: unit('minimum') }
}

function parseGuidance(raw: unknown): SlipPrecheck['guidance'] {
  if (raw === null) return null
  const r = object(raw, 'guidance', ['key', 'text_hi', 'text_en'])
  return { key: oneOf(r, 'key', 'guidance', PRECHECK_GUIDANCE_KEYS), text_hi: text(r, 'text_hi', 'guidance'), text_en: text(r, 'text_en', 'guidance') }
}

function parseNextAction(raw: unknown): SlipPrecheck['next_action'] {
  const r = object(raw, 'next_action', ['kind', 'label_hi', 'label_en'])
  return { kind: oneOf(r, 'kind', 'next_action', PRECHECK_ACTION_KINDS), label_hi: text(r, 'label_hi', 'next_action'), label_en: text(r, 'label_en', 'next_action') }
}

function parseDocument(raw: unknown): SlipPrecheck['document'] {
  const r = object(raw, 'document', ['type', 'accepted'])
  const type = r.type === null ? null : oneOf(r, 'type', 'document', DOCUMENT_TYPES)
  if (typeof r.accepted !== 'boolean') fail('document.accepted', 'expected true or false')
  if (r.accepted !== (type !== null && type !== 'other')) fail('document.accepted', 'accepted is true for the four medical types only')
  return { type, accepted: r.accepted }
}

const KEYS = [
  'precheck_id', 'merchant_id', 'status', 'attempt', 'retakes_left', 'media_id', 'document', 'slots', 'checklist', 'gate', 'reason', 'guidance',
  'next_action', 'source', 'mode', 'provider', 'model', 'fallback_reason', 'attempts',
] as const

/** READY asks the merchant to confirm; RETAKE and NEEDS_TEAM carry a reason and a guidance line and one way on. */
function checkStatusRules(check: SlipPrecheck): void {
  const { status, reason, guidance, next_action: action } = check
  if ((reason === null) !== (guidance === null)) fail('guidance', 'a reason and a guidance line go together')
  if (status === 'READY') {
    if (reason !== null) fail('reason', 'a READY check has no reason')
    if (action.kind !== 'CONFIRM_FIELDS') fail('next_action.kind', 'a READY check asks to CONFIRM_FIELDS')
  } else if (status === 'RETAKE' || status === 'NEEDS_TEAM') {
    if (reason === null) fail('reason', `a ${status} check names its reason`)
    const expected = status === 'RETAKE' ? 'RETAKE_PHOTO' : 'SEND_TO_TEAM'
    if (action.kind !== expected && !(status === 'RETAKE' && action.kind === 'SEND_TO_TEAM' && guidance?.key === 'SLIP_PHOTO_LIMIT')) fail('next_action.kind', `a ${status} check offers ${expected}`)
  }
}

/** The label is honest (ADR 0004): SIMULATED and FALLBACK never read as LIVE, and a live provider is not called simulated. */
function checkLabel(check: SlipPrecheck): void {
  const { mode, provider, fallback_reason: reason, source } = check
  if (mode === 'SIMULATED' && provider !== 'simulated' && provider !== 'mock') fail('provider', 'a SIMULATED answer names the simulator or the mock')
  if (mode === 'LIVE' && (provider === 'simulated' || provider === 'mock' || provider === 'none')) fail('provider', 'a LIVE answer names a live provider')
  if (mode === 'FALLBACK' && reason === null) fail('fallback_reason', 'a FALLBACK answer says why')
  if (mode === 'LIVE' && reason !== null) fail('fallback_reason', 'a LIVE answer has no fallback reason')
  if (source.kind !== 'SLIP') fail('source.kind', 'expected SLIP')
  if (mode === 'LIVE' && source.origin !== 'LIVE') fail('source.origin', 'a LIVE read has a LIVE source')
  if (mode === 'SIMULATED' && source.origin === 'LIVE') fail('source.origin', 'a SIMULATED read cannot have a LIVE source')
}

/**
 * The backend sends the slip source with its Hindi label (`label_hi`) beside the English one. The screens keep their own
 * Hindi copy, so the label is checked as text and dropped; every other extra field is still a contract error.
 */
function parseSlipSource(raw: unknown): Source {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw) || !('label_hi' in raw)) return parseSource(raw, 'source')
  const { label_hi: labelHi, ...rest } = raw as Record<string, unknown>
  if (typeof labelHi !== 'string' || labelHi.trim() === '') fail('source.label_hi', 'expected text')
  return parseSource(rest, 'source')
}

export function parsePrecheck(raw: unknown): SlipPrecheck {
  const r = object(raw, 'precheck', KEYS)
  const attempt = whole(r, 'attempt', 'precheck', 1, MAX_PHOTOS)
  const retakesLeft = whole(r, 'retakes_left', 'precheck', 0, MAX_PHOTOS - 1)
  if (attempt + retakesLeft !== MAX_PHOTOS) fail('precheck.retakes_left', `attempt and retakes_left add up to ${MAX_PHOTOS}`)
  const check: SlipPrecheck = {
    precheck_id: matching(r, 'precheck_id', 'precheck', PRECHECK_ID, 'an id like PC-000001'),
    merchant_id: matching(r, 'merchant_id', 'precheck', MERCHANT_ID, 'an id like S-0142'),
    status: oneOf(r, 'status', 'precheck', PRECHECK_STATUSES),
    attempt,
    retakes_left: retakesLeft,
    media_id: matching(r, 'media_id', 'precheck', MEDIA_ID, 'an id like MD-000002'),
    document: parseDocument(r.document),
    slots: parseSlots(r.slots),
    checklist: parseChecklist(r.checklist),
    gate: parseGate(r.gate),
    reason: r.reason === null ? null : oneOf(r, 'reason', 'precheck', PRECHECK_REASONS),
    guidance: parseGuidance(r.guidance),
    next_action: parseNextAction(r.next_action),
    source: parseSlipSource(r.source),
    mode: oneOf(r, 'mode', 'precheck', MODES),
    provider: oneOf(r, 'provider', 'precheck', PROVIDERS),
    model: textOrNull(r, 'model', 'precheck'),
    fallback_reason: textOrNull(r, 'fallback_reason', 'precheck'),
    attempts: parseAttempts(r.attempts),
  }
  checkStatusRules(check)
  checkLabel(check)
  return check
}

const CONFIRM_KEYS = ['precheck_id', 'status', 'confirmed_as', 'claim_id', 'decision_id', 'outcome', 'case_id', 'messages', 'consent', 'doctor_check'] as const
const CONSENT_KEYS = ['purpose', 'status', 'precheck_id', 'doctor_name', 'hospital_name', 'question_hi', 'question_en', 'answered_at'] as const

function idOrNull(record: Json, key: string, path: string, pattern: RegExp, hint: string): string | null {
  return record[key] === null ? null : matching(record, key, path, pattern, hint)
}

/** The doctor question (design 2.4): the server's words in both languages, the answer and its time once given. */
export function parseDoctorConsent(raw: unknown, path = 'consent'): DoctorConsent {
  const r = object(raw, path, CONSENT_KEYS)
  const status = oneOf(r, 'status', path, DOCTOR_CONSENT_STATUSES)
  const answeredAt = idOrNull(r, 'answered_at', path, ISO_TIME, 'a time like 2025-08-21T11:21:00+05:30')
  if ((status === 'ASKED') !== (answeredAt === null)) fail(at(path, 'answered_at'), 'an answered question has its time, and an open one none')
  const questionHi = text(r, 'question_hi', path)
  const questionEn = text(r, 'question_en', path)
  if (questionHi.trim() === '' || questionEn.trim() === '') fail(path, 'the question is asked in Hindi and in English')
  return {
    purpose: oneOf(r, 'purpose', path, [DOCTOR_CONSENT_PURPOSE] as const),
    status,
    precheck_id: matching(r, 'precheck_id', path, PRECHECK_ID, 'an id like PC-000001'),
    doctor_name: textOrNull(r, 'doctor_name', path),
    hospital_name: textOrNull(r, 'hospital_name', path),
    question_hi: questionHi,
    question_en: questionEn,
    answered_at: answeredAt,
  }
}

function parseDoctorCheck(raw: unknown): DoctorCheck | null {
  if (raw === null || raw === undefined) return null
  const r = object(raw, 'confirm.doctor_check', ['status', 'doctor_name', 'hospital_name'])
  return {
    status: oneOf(r, 'status', 'confirm.doctor_check', ['PENDING'] as const),
    doctor_name: textOrNull(r, 'doctor_name', 'confirm.doctor_check'),
    hospital_name: textOrNull(r, 'hospital_name', 'confirm.doctor_check'),
  }
}

/** AWAITING_CONSENT files nothing and asks; CONFIRMED names the claim; a case goes with REFERRED unless the doctor is still asked. */
function checkConfirmRules(done: PrecheckConfirm): void {
  const filed = [done.claim_id, done.decision_id, done.outcome]
  if (done.status === 'AWAITING_CONSENT') {
    if (filed.some((value) => value !== null) || done.case_id !== null) fail('confirm.status', 'an AWAITING_CONSENT answer has no claim, decision, outcome or case yet')
    if (done.consent === null) fail('confirm.consent', 'an AWAITING_CONSENT answer carries the doctor question')
    if (done.consent.status !== 'ASKED') fail('confirm.consent.status', 'the open question is ASKED')
    return
  }
  if (filed.some((value) => value === null)) fail('confirm.status', 'a CONFIRMED answer names its claim, decision and outcome')
  const waiting = done.doctor_check?.status === 'PENDING'
  if (done.outcome === 'REFERRED' && done.case_id === null && !waiting) fail('confirm.case_id', 'a REFERRED claim has a case unless the doctor is still being asked')
  if (done.outcome !== 'REFERRED' && done.case_id !== null) fail('confirm.case_id', 'a REFERRED claim has a case, and no other outcome does')
}

/** POST .../confirm (design 2.4). A server without the doctor keys (the rule off) reads as `consent: null, doctor_check: null`. */
export function parsePrecheckConfirm(raw: unknown): PrecheckConfirm {
  const withKeys = typeof raw === 'object' && raw !== null && !Array.isArray(raw) ? { consent: null, doctor_check: null, ...raw } : raw
  const r = object(withKeys, 'confirm', CONFIRM_KEYS)
  const done: PrecheckConfirm = {
    precheck_id: matching(r, 'precheck_id', 'confirm', PRECHECK_ID, 'an id like PC-000001'),
    status: oneOf(r, 'status', 'confirm', ['AWAITING_CONSENT', 'CONFIRMED'] as const),
    confirmed_as: oneOf(r, 'confirmed_as', 'confirm', ['FIELDS_CONFIRMED', 'SENT_TO_TEAM'] as const),
    claim_id: idOrNull(r, 'claim_id', 'confirm', CLAIM_ID, 'an id like CL-000001'),
    decision_id: idOrNull(r, 'decision_id', 'confirm', DECISION_ID, 'an id like D-000001'),
    outcome: r.outcome === null ? null : oneOf(r, 'outcome', 'confirm', OUTCOMES),
    case_id: idOrNull(r, 'case_id', 'confirm', CASE_ID, 'an id like C-2291'),
    messages: array(r.messages, 'confirm.messages') as PrecheckConfirm['messages'],
    consent: r.consent === null ? null : parseDoctorConsent(r.consent, 'confirm.consent'),
    doctor_check: parseDoctorCheck(r.doctor_check),
  }
  checkConfirmRules(done)
  return done
}

const OPEN_KEYS = ['merchant_id', 'checkin_open', 'first_silent_day', 'precheck', 'awaiting_consent'] as const

/** GET .../slip-precheck/open (design 2.4): at most one of the open pre-check and the waiting question, and only while a check-in is open. */
export function parsePrecheckOpen(raw: unknown): PrecheckOpen {
  const r = object(raw, 'open', OPEN_KEYS)
  if (typeof r.checkin_open !== 'boolean') fail('open.checkin_open', 'expected true or false')
  const open: PrecheckOpen = {
    merchant_id: matching(r, 'merchant_id', 'open', MERCHANT_ID, 'an id like S-0142'),
    checkin_open: r.checkin_open,
    first_silent_day: idOrNull(r, 'first_silent_day', 'open', ISO_DATE, 'a date like 2025-08-20'),
    precheck: r.precheck === null ? null : parsePrecheck(r.precheck),
    awaiting_consent: r.awaiting_consent === null ? null : parseDoctorConsent(r.awaiting_consent, 'open.awaiting_consent'),
  }
  if (!open.checkin_open && (open.precheck !== null || open.awaiting_consent !== null || open.first_silent_day !== null)) fail('open.checkin_open', 'nothing is open without a check-in')
  if (open.precheck !== null && open.awaiting_consent !== null) fail('open.awaiting_consent', 'either a pre-check or the doctor question waits, not both')
  if (open.awaiting_consent !== null && open.awaiting_consent.status !== 'ASKED') fail('open.awaiting_consent.status', 'the waiting question is ASKED')
  return open
}
