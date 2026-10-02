/**
 * Types and strict parsers of the rights routes (data-model 5.4 and 5.5, fs-06 section 8, fs-07 section 9.6): the
 * grievance ladder, the consent centre, the activity log, the withdrawal and the erase of a slip. A body that does not
 * match raises `ContractViolation` and the screen shows `contract_violation`; nothing is guessed. The closed lists
 * are the ones of the contract. Every parser takes `unknown` and returns a new value.
 */
import { ContractViolation } from './parse'

export const GRIEVANCE_KINDS = ['DISPUTE', 'COMPLAINT'] as const
export const GRIEVANCE_TOPICS = [
  'PAYOUT_AMOUNT',
  'CLAIM_DECLINED',
  'CLAIM_SLOW',
  'EDI_HOLIDAY',
  'PAYMENT_NOT_RECEIVED',
  'PREMIUM_CHARGE',
  'DATA_OR_CONSENT',
  'APP_ISSUE',
  'OTHER',
] as const
export const RESPONDENTS = ['INSURER', 'LENDER', 'PAYTM'] as const
export const STEP_IDS = ['PAYTM_DISPUTE', 'INSURER_GRO', 'BIMA_BHAROSA', 'OMBUDSMAN', 'LENDER_GRIEVANCE', 'PAYTM_SUPPORT'] as const
export const GRIEVANCE_STATUSES = ['OPEN', 'RESOLVED'] as const
export const STEP_STATES = ['NOT_STARTED', 'ACTIVE', 'DONE'] as const
export const DELIVERIES = ['IN_CHHATRI', 'SIMULATED', 'SELF_REPORTED'] as const
export const CLOCK_KINDS = ['OWN_SLA', 'PORTAL_STATED', 'TO_CONFIRM'] as const
export const CONSENT_PURPOSES = ['SALES_DATA_FOR_CLAIM', 'SLIP_DATA_FOR_HOSPITAL_CLAIM', 'SETTLEMENT_DEDUCTION'] as const
export const CONSENT_STATUSES = ['ACTIVE', 'WITHDRAWN', 'NOT_GIVEN'] as const
export const CONSENT_SOURCES = ['PAYMENT_APP', 'PAYMENT_CHAT', 'SLIP_UPLOAD', 'SEEDED'] as const
export const ACTIVITY_KINDS = ['USED', 'GRANTED', 'WITHDRAWN', 'EFFECT', 'ERASED'] as const
export const COVER_AFTER = ['NONE', 'WAITING', 'ACTIVE', 'LAPSED', 'CANCELLED', 'PENDING_PAYMENT'] as const
export const MAX_COMPLAINT_CHARS = 500
/** The respondent router of fs-06 7.1: a fixed lookup in code, never a model (the server holds the same lookup). */
export const TOPIC_RESPONDENT: Readonly<Record<(typeof GRIEVANCE_TOPICS)[number], (typeof RESPONDENTS)[number]>> = {
  PAYOUT_AMOUNT: 'INSURER',
  CLAIM_DECLINED: 'INSURER',
  CLAIM_SLOW: 'INSURER',
  EDI_HOLIDAY: 'LENDER',
  PAYMENT_NOT_RECEIVED: 'PAYTM',
  PREMIUM_CHARGE: 'PAYTM',
  DATA_OR_CONSENT: 'PAYTM',
  APP_ISSUE: 'PAYTM',
  OTHER: 'PAYTM',
}

export type GrievanceKind = (typeof GRIEVANCE_KINDS)[number]
export type GrievanceTopic = (typeof GRIEVANCE_TOPICS)[number]
export type Respondent = (typeof RESPONDENTS)[number]
export type StepId = (typeof STEP_IDS)[number]
export type StepState = (typeof STEP_STATES)[number]
export type Delivery = (typeof DELIVERIES)[number]
export type ConsentPurpose = (typeof CONSENT_PURPOSES)[number]
export type ConsentStatus = (typeof CONSENT_STATUSES)[number]
export type ActivityKind = (typeof ACTIVITY_KINDS)[number]

/** A clock exists only where a source does (fs-06 7.2). `state` and `day` are optional extras the server may add. */
export type LadderClock =
  | { kind: 'OWN_SLA'; hours: number; due_by: string; state: string | null }
  | { kind: 'PORTAL_STATED'; days: number; started_at: string | null; statement_en: string; state: string | null }
  | { kind: 'TO_CONFIRM'; note_en: string }

export type LadderStep = { level: number; id: StepId; name: string; state: StepState; delivery: Delivery; entered_at: string | null; clock: LadderClock }
export type NextAction = { id: string; label_en: string }
export type Grievance = {
  grievance_id: string
  kind: GrievanceKind
  topic: GrievanceTopic
  respondent: Respondent
  decision_id: string | null
  case_id: string | null
  status: 'OPEN' | 'RESOLVED'
  opened_at: string
  current_step: StepId
  ladder_steps: LadderStep[]
  next_action: NextAction | null
}

export type HeldSlip = { slip_id: string; claim_id: string; received_at: string; state: 'HELD' | 'ERASED'; erased_at: string | null; can_erase: boolean; blocked_reason: string | null }
export type Consent = {
  consent_id: string | null
  purpose: ConsentPurpose
  purpose_label_en: string
  purpose_label_hi: string
  status: ConsentStatus
  granted_at: string | null
  withdrawn_at: string | null
  source: (typeof CONSENT_SOURCES)[number] | null
  notice_version: string | null
  current_notice_version: string
  required_to_buy: boolean
  data_used_en: string[]
  data_used_hi: string[]
  withdraw_effect_en: string
  withdraw_effect_hi: string
  can_withdraw: boolean
  blocked_reason: string | null
  regrant_en: string
  regrant_hi: string
  held: HeldSlip[] | null
}
export type WithdrawResult = {
  consent_id: string
  purpose: ConsentPurpose
  status: 'WITHDRAWN'
  withdrawn_at: string
  action_taken_en: string
  action_taken_hi: string
  cover_status: (typeof COVER_AFTER)[number]
}
export type ActivityItem = { seq: number; at: string; purpose: ConsentPurpose; kind: ActivityKind; text_en: string; text_hi: string; ref: { type: string; id: string } | null }
export type ForgetResult = {
  slip_id: string
  claim_id: string
  erased_at: string
  erased: { photo: boolean; claim_fields: boolean; decisions: number; case_fields: number; messages: number }
  kept: string[]
  audit_note_en: string
  audit_note_hi: string
}

type Json = Readonly<Record<string, unknown>>

const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const GRIEVANCE_ID = /^GR-\d{6,}$/
const CONSENT_ID = /^CN-\d{6,}$/
const DECISION_ID = /^D-\d{6,}$/
const CASE_ID = /^C-\d+$/
const CLAIM_ID = /^CL-\d{6,}$/
const SLIP_ID = /^MD-\d{6,}$/

export const isGrievanceId = (value: string): boolean => GRIEVANCE_ID.test(value)
export const isConsentId = (value: string): boolean => CONSENT_ID.test(value)
export const isSlipId = (value: string): boolean => SLIP_ID.test(value)
export const isIsoDate = (value: string): boolean => ISO_DATE.test(value)

const isNil = (value: unknown): boolean => value === null || value === undefined

function fail(path: string, problem: string): never {
  throw new ContractViolation(`${path}: ${problem}`)
}

function shape(value: unknown, path: string, required: readonly string[], optional: readonly string[] = []): Json {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'expected an object')
  const record = value as Json
  const unknown = Object.keys(record).filter((key) => !required.includes(key) && !optional.includes(key))
  if (unknown.length > 0) fail(path, `unknown field ${unknown.join(', ')}`)
  const missing = required.filter((key) => !(key in record))
  if (missing.length > 0) fail(path, `missing field ${missing.join(', ')}`)
  return record
}

const at = (path: string, key: string): string => `${path}.${key}`
const items = (value: unknown, path: string): readonly unknown[] => (Array.isArray(value) ? value : fail(path, 'expected a list'))

function text(record: Json, key: string, path: string): string {
  const value = record[key]
  return typeof value === 'string' ? value : fail(at(path, key), 'expected text')
}
const textOrNull = (record: Json, key: string, path: string): string | null => (isNil(record[key]) ? null : text(record, key, path))

function whole(record: Json, key: string, path: string): number {
  const value = record[key]
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : fail(at(path, key), 'expected a whole number')
}

function flag(record: Json, key: string, path: string): boolean {
  const value = record[key]
  return typeof value === 'boolean' ? value : fail(at(path, key), 'expected true or false')
}

function pick<T extends string>(record: Json, key: string, path: string, allowed: readonly T[]): T {
  const value = record[key]
  return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? (value as T) : fail(at(path, key), `expected one of ${allowed.join(', ')}`)
}

function like(record: Json, key: string, path: string, pattern: RegExp, hint: string): string {
  const value = text(record, key, path)
  return pattern.test(value) ? value : fail(at(path, key), `expected ${hint}`)
}
const likeOrNull = (record: Json, key: string, path: string, pattern: RegExp, hint: string): string | null => (isNil(record[key]) ? null : like(record, key, path, pattern, hint))
const time = (record: Json, key: string, path: string): string => like(record, key, path, ISO_TIME, 'a timestamp with a time zone')
const timeOrNull = (record: Json, key: string, path: string): string | null => likeOrNull(record, key, path, ISO_TIME, 'a timestamp with a time zone')

function textList(record: Json, key: string, path: string): string[] {
  return items(record[key], at(path, key)).map((entry, index) => (typeof entry === 'string' ? entry : fail(`${at(path, key)}[${index}]`, 'expected text')))
}

/** The day a merchant says they filed: a date, or a timestamp. */
function timeOrDate(record: Json, key: string, path: string): string | null {
  if (isNil(record[key])) return null
  const value = text(record, key, path)
  return ISO_TIME.test(value) || ISO_DATE.test(value) ? value : fail(at(path, key), 'expected a date or a timestamp')
}

function parseClock(raw: unknown, path: string): LadderClock {
  const kind = pick(shape(raw, path, ['kind'], ['hours', 'due_by', 'state', 'days', 'started_at', 'statement_en', 'note_en', 'day', 'ends_on']), 'kind', path, ['OWN_SLA', 'PORTAL_STATED', 'TO_CONFIRM'] as const)
  const record = raw as Json
  if (kind === 'OWN_SLA') return { kind, hours: whole(record, 'hours', path), due_by: time(record, 'due_by', path), state: textOrNull(record, 'state', path) }
  if (kind === 'PORTAL_STATED') {
    return { kind, days: whole(record, 'days', path), started_at: timeOrDate(record, 'started_at', path), statement_en: text(record, 'statement_en', path), state: textOrNull(record, 'state', path) }
  }
  return { kind, note_en: text(record, 'note_en', path) }
}

function parseStep(raw: unknown, path: string): LadderStep {
  const record = shape(raw, path, ['level', 'id', 'name', 'state', 'delivery', 'clock'], ['entered_at'])
  return {
    level: whole(record, 'level', path),
    id: pick(record, 'id', path, STEP_IDS),
    name: text(record, 'name', path),
    state: pick(record, 'state', path, STEP_STATES),
    delivery: pick(record, 'delivery', path, DELIVERIES),
    entered_at: timeOrNull(record, 'entered_at', path),
    clock: parseClock(record.clock, at(path, 'clock')),
  }
}

function parseNext(raw: unknown, path: string): NextAction | null {
  if (raw === null) return null
  const record = shape(raw, path, ['id', 'label_en'])
  return { id: text(record, 'id', path), label_en: text(record, 'label_en', path) }
}

export function parseGrievance(raw: unknown, path = 'grievance'): Grievance {
  const record = shape(raw, path, ['grievance_id', 'kind', 'topic', 'respondent', 'decision_id', 'case_id', 'status', 'opened_at', 'current_step', 'ladder_steps', 'next_action'])
  const steps = items(record.ladder_steps, at(path, 'ladder_steps')).map((step, index) => parseStep(step, `${path}.ladder_steps[${index}]`))
  const current = pick(record, 'current_step', path, STEP_IDS)
  if (steps.length === 0) fail(at(path, 'ladder_steps'), 'expected at least one step')
  if (!steps.some((step) => step.id === current)) fail(at(path, 'current_step'), 'is not a step of the ladder')
  return {
    grievance_id: like(record, 'grievance_id', path, GRIEVANCE_ID, 'an id like GR-000001'),
    kind: pick(record, 'kind', path, GRIEVANCE_KINDS),
    topic: pick(record, 'topic', path, GRIEVANCE_TOPICS),
    respondent: pick(record, 'respondent', path, RESPONDENTS),
    decision_id: likeOrNull(record, 'decision_id', path, DECISION_ID, 'an id like D-000142'),
    case_id: likeOrNull(record, 'case_id', path, CASE_ID, 'an id like C-2291'),
    status: pick(record, 'status', path, GRIEVANCE_STATUSES),
    opened_at: time(record, 'opened_at', path),
    current_step: current,
    ladder_steps: steps,
    next_action: parseNext(record.next_action, at(path, 'next_action')),
  }
}

export function parseGrievances(raw: unknown): Grievance[] {
  return items(raw, 'grievances').map((entry, index) => parseGrievance(entry, `grievances[${index}]`))
}

function parseHeld(raw: unknown, path: string): HeldSlip {
  const record = shape(raw, path, ['slip_id', 'claim_id', 'received_at', 'state', 'erased_at', 'can_erase', 'blocked_reason'])
  return {
    slip_id: like(record, 'slip_id', path, SLIP_ID, 'an id like MD-000002'),
    claim_id: like(record, 'claim_id', path, CLAIM_ID, 'an id like CL-000001'),
    received_at: time(record, 'received_at', path),
    state: pick(record, 'state', path, ['HELD', 'ERASED'] as const),
    erased_at: timeOrNull(record, 'erased_at', path),
    can_erase: flag(record, 'can_erase', path),
    blocked_reason: textOrNull(record, 'blocked_reason', path),
  }
}

const CONSENT_KEYS = [
  'consent_id', 'purpose', 'purpose_label_en', 'purpose_label_hi', 'status', 'granted_at', 'withdrawn_at', 'source', 'notice_version',
  'current_notice_version', 'required_to_buy', 'data_used_en', 'data_used_hi', 'withdraw_effect_en', 'withdraw_effect_hi', 'can_withdraw',
  'blocked_reason', 'regrant_en', 'regrant_hi',
] as const

function parseConsent(raw: unknown, path: string): Consent {
  const record = shape(raw, path, CONSENT_KEYS, ['held'])
  const purpose = pick(record, 'purpose', path, CONSENT_PURPOSES)
  const status = pick(record, 'status', path, CONSENT_STATUSES)
  const consentId = likeOrNull(record, 'consent_id', path, CONSENT_ID, 'an id like CN-000002')
  if ((status === 'NOT_GIVEN') !== (consentId === null)) fail(at(path, 'consent_id'), 'is null exactly when the status is NOT_GIVEN')
  const held = isNil(record.held) ? null : items(record.held, at(path, 'held')).map((slip, index) => parseHeld(slip, `${path}.held[${index}]`))
  if (held !== null && purpose !== 'SLIP_DATA_FOR_HOSPITAL_CLAIM') fail(at(path, 'held'), 'only the slip item holds slips')
  return {
    consent_id: consentId,
    purpose,
    purpose_label_en: text(record, 'purpose_label_en', path),
    purpose_label_hi: text(record, 'purpose_label_hi', path),
    status,
    granted_at: timeOrNull(record, 'granted_at', path),
    withdrawn_at: timeOrNull(record, 'withdrawn_at', path),
    source: record.source === null ? null : pick(record, 'source', path, CONSENT_SOURCES),
    notice_version: textOrNull(record, 'notice_version', path),
    current_notice_version: text(record, 'current_notice_version', path),
    required_to_buy: flag(record, 'required_to_buy', path),
    data_used_en: textList(record, 'data_used_en', path),
    data_used_hi: textList(record, 'data_used_hi', path),
    withdraw_effect_en: text(record, 'withdraw_effect_en', path),
    withdraw_effect_hi: text(record, 'withdraw_effect_hi', path),
    can_withdraw: flag(record, 'can_withdraw', path),
    blocked_reason: textOrNull(record, 'blocked_reason', path),
    regrant_en: text(record, 'regrant_en', path),
    regrant_hi: text(record, 'regrant_hi', path),
    held,
  }
}

export function parseConsents(raw: unknown): Consent[] {
  const list = items(raw, 'consents').map((entry, index) => parseConsent(entry, `consents[${index}]`))
  const purposes = list.map((consent) => consent.purpose)
  if (list.length !== CONSENT_PURPOSES.length || CONSENT_PURPOSES.some((purpose, index) => purposes[index] !== purpose)) {
    fail('consents', 'expected the three purposes in the order sales, slip, settlement')
  }
  return list
}

export function parseWithdraw(raw: unknown): WithdrawResult {
  const path = 'withdraw'
  const record = shape(raw, path, ['consent_id', 'purpose', 'status', 'withdrawn_at', 'action_taken_en', 'action_taken_hi', 'cover_status'])
  return {
    consent_id: like(record, 'consent_id', path, CONSENT_ID, 'an id like CN-000002'),
    purpose: pick(record, 'purpose', path, CONSENT_PURPOSES),
    status: pick(record, 'status', path, ['WITHDRAWN'] as const),
    withdrawn_at: time(record, 'withdrawn_at', path),
    action_taken_en: text(record, 'action_taken_en', path),
    action_taken_hi: text(record, 'action_taken_hi', path),
    cover_status: pick(record, 'cover_status', path, COVER_AFTER),
  }
}

function parseActivityItem(raw: unknown, path: string): ActivityItem {
  const record = shape(raw, path, ['seq', 'at', 'purpose', 'kind', 'text_en', 'text_hi', 'ref'])
  let ref: ActivityItem['ref'] = null
  if (record.ref !== null) {
    const link = shape(record.ref, at(path, 'ref'), ['type', 'id'])
    ref = { type: text(link, 'type', at(path, 'ref')), id: text(link, 'id', at(path, 'ref')) }
  }
  return {
    seq: whole(record, 'seq', path),
    at: time(record, 'at', path),
    purpose: pick(record, 'purpose', path, CONSENT_PURPOSES),
    kind: pick(record, 'kind', path, ACTIVITY_KINDS),
    text_en: text(record, 'text_en', path),
    text_hi: text(record, 'text_hi', path),
    ref,
  }
}

export function parseActivity(raw: unknown): ActivityItem[] {
  return items(raw, 'activity').map((entry, index) => parseActivityItem(entry, `activity[${index}]`))
}

export function parseForget(raw: unknown): ForgetResult {
  const path = 'forget'
  const record = shape(raw, path, ['slip_id', 'claim_id', 'erased_at', 'erased', 'kept', 'audit_note_en', 'audit_note_hi'])
  const erased = shape(record.erased, at(path, 'erased'), ['photo', 'claim_fields', 'decisions', 'case_fields', 'messages'])
  return {
    slip_id: like(record, 'slip_id', path, SLIP_ID, 'an id like MD-000002'),
    claim_id: like(record, 'claim_id', path, CLAIM_ID, 'an id like CL-000001'),
    erased_at: time(record, 'erased_at', path),
    erased: {
      photo: flag(erased, 'photo', at(path, 'erased')),
      claim_fields: flag(erased, 'claim_fields', at(path, 'erased')),
      decisions: whole(erased, 'decisions', at(path, 'erased')),
      case_fields: whole(erased, 'case_fields', at(path, 'erased')),
      messages: whole(erased, 'messages', at(path, 'erased')),
    },
    kept: textList(record, 'kept', path),
    audit_note_en: text(record, 'audit_note_en', path),
    audit_note_hi: text(record, 'audit_note_hi', path),
  }
}
