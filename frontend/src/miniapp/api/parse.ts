/**
 * Strict view-model parsers for the mini-app's routes (fs-04 section 6.5 and 9.4, data-model 5.1 and 5.8).
 *
 * The app never guesses. A body with an unknown field, a value outside its enum, a money label that is not the
 * formatted paise, or an impossible combination (an AREA claim that is REFERRED, a REFERRED claim with no case, a
 * DISPUTE with steps, a number with no source) raises `ContractViolation`, and the screen shows its error state with
 * the code `contract_violation`. Every parser takes `unknown` and returns a new, typed value.
 */
import { ApiError } from '../../api/client'
import {
  CLAIM_KINDS,
  COUNTERFACTUAL_KINDS,
  COVER_STATUSES,
  LENDER_REASON_CODES,
  SOURCE_KINDS,
  STEP_NAMES,
  STEP_STATUSES,
  type ClaimItem,
  type ClaimStep,
  type Counterfactual,
  type Cover,
  type CoverQuote,
  type Receipt,
  type ReceiptCheck,
  type ReceiptEdi,
  type ReceiptFact,
  type PremiumLinkResult,
  type PremiumPayment,
  type Source,
} from '../../api/types'
import { formatInr } from '../../lib/money'

export class ContractViolation extends ApiError {
  constructor(message: string) {
    super('contract_violation', message, 0)
    this.name = 'ContractViolation'
  }
}

type Json = Readonly<Record<string, unknown>>

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/
const MERCHANT_ID = /^S-\d{4}$/
const DECISION_ID = /^D-\d{6,}$/
const CLAIM_ID = /^CL-\d{6,}$/
const HASH_PREFIX = /^[0-9a-f]{12}$/
const OUTCOMES = ['APPROVED', 'REFERRED', 'DECLINED'] as const
const EDI_RESULTS = ['GRANTED', 'REFUSED', 'NO_LOAN', 'NO_RESPONSE'] as const
const CASE_KINDS = ['PERSONAL_CLAIM_REVIEW', 'DISPUTE', 'AREA_REVIEW'] as const
const CASE_STATUSES = ['OPEN', 'APPROVED', 'DECLINED', 'CLOSED'] as const
const CHECK_STATUSES = ['PASS', 'FAIL', 'UNSURE', 'NOT_APPLICABLE', 'WAIVED_BY_OFFICER'] as const
const SEVERITIES = ['HARD', 'SOFT'] as const
const ORIGINS = ['LIVE', 'SIMULATED', 'CONFIG'] as const
const PAYOUT_STATUSES = ['PENDING', 'CREDITED', 'FAILED'] as const
const HOLIDAY_STATUSES = ['REQUESTED', 'GRANTED', 'REFUSED', 'NO_RESPONSE'] as const
const QUOTE_OUTCOMES = ['OK', 'BLOCKED'] as const
const PREMIUM_METHODS = ['SETTLEMENT_DEDUCTION', 'PAYMENT_LINK'] as const
const PREMIUM_STATUSES = ['PENDING', 'PAID', 'FAILED', 'EXPIRED'] as const

function fail(path: string, problem: string): never {
  throw new ContractViolation(`${path}: ${problem}`)
}

/** An object with exactly these keys: an unknown or a missing field is a violation. */
function object(value: unknown, path: string, keys: readonly string[]): Json {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'expected an object')
  const record = value as Json
  const unknown = Object.keys(record).filter((key) => !keys.includes(key))
  if (unknown.length > 0) fail(path, `unknown field ${unknown.join(', ')}`)
  const missing = keys.filter((key) => !(key in record))
  if (missing.length > 0) fail(path, `missing field ${missing.join(', ')}`)
  return record
}

function list(value: unknown, path: string): readonly unknown[] {
  return Array.isArray(value) ? value : fail(path, 'expected a list')
}

const where = (path: string, key: string): string => `${path}.${key}`

function text(record: Json, key: string, path: string): string {
  const value = record[key]
  return typeof value === 'string' ? value : fail(where(path, key), 'expected text')
}

function textOrNull(record: Json, key: string, path: string): string | null {
  return record[key] === null ? null : text(record, key, path)
}

function integer(record: Json, key: string, path: string): number {
  const value = record[key]
  return typeof value === 'number' && Number.isSafeInteger(value) ? value : fail(where(path, key), 'expected a whole number')
}

function boolean(record: Json, key: string, path: string): boolean {
  const value = record[key]
  return typeof value === 'boolean' ? value : fail(where(path, key), 'expected true or false')
}

function oneOf<T extends string>(record: Json, key: string, path: string, allowed: readonly T[]): T {
  const value = record[key]
  return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? (value as T) : fail(where(path, key), `expected one of ${allowed.join(', ')}`)
}

function oneOfOrNull<T extends string>(record: Json, key: string, path: string, allowed: readonly T[]): T | null {
  return record[key] === null ? null : oneOf(record, key, path, allowed)
}

function matching(record: Json, key: string, path: string, pattern: RegExp, hint: string): string {
  const value = text(record, key, path)
  return pattern.test(value) ? value : fail(where(path, key), `expected ${hint}`)
}

function matchingOrNull(record: Json, key: string, path: string, pattern: RegExp, hint: string): string | null {
  return record[key] === null ? null : matching(record, key, path, pattern, hint)
}

const isoDate = (record: Json, key: string, path: string): string => matching(record, key, path, ISO_DATE, 'a date like 2025-08-25')
const isoDateOrNull = (record: Json, key: string, path: string): string | null => matchingOrNull(record, key, path, ISO_DATE, 'a date like 2025-08-25')
const isoTime = (record: Json, key: string, path: string): string => matching(record, key, path, ISO_TIME, 'a timestamp with a time zone')
const isoTimeOrNull = (record: Json, key: string, path: string): string | null => matchingOrNull(record, key, path, ISO_TIME, 'a timestamp with a time zone')

/** Integer paise and its label: the label must be the formatted paise, so no screen shows a number the API did not make. */
function money(record: Json, paiseKey: string, labelKey: string, path: string): { paise: number; label: string } {
  const paise = integer(record, paiseKey, path)
  const label = text(record, labelKey, path)
  return label === formatInr(paise) ? { paise, label } : fail(where(path, labelKey), `expected ${formatInr(paise)} for ${paise} paise`)
}

/** Both null, or both set and consistent. */
function moneyOrNull(record: Json, paiseKey: string, labelKey: string, path: string): { paise: number | null; label: string | null } {
  if (record[paiseKey] === null && record[labelKey] === null) return { paise: null, label: null }
  if (record[paiseKey] === null || record[labelKey] === null) return fail(where(path, labelKey), `${paiseKey} and ${labelKey} must both be set or both be null`)
  return money(record, paiseKey, labelKey, path)
}

const COVER_KEYS = [
  'merchant_id', 'cover_id', 'status', 'status_text_hi', 'status_text_en', 'zone_id', 'zone_name', 'purchased_at', 'starts_on',
  'prepaid_through', 'waiting_period_days', 'premium_per_day_paise', 'premium_per_day_label', 'premium_due', 'annual_limit_paise',
  'annual_limit_label', 'amount_claimed_paise', 'amount_claimed_label', 'amount_remaining_paise', 'amount_remaining_label',
  'alert_active', 'alert_id',
] as const

/** GET /api/merchants/{id}/cover. */
export function parseCover(raw: unknown): Cover {
  const path = 'cover'
  const r = object(raw, path, COVER_KEYS)
  const status = oneOf(r, 'status', path, COVER_STATUSES)
  const coverId = textOrNull(r, 'cover_id', path)
  if (status === 'NONE' && coverId !== null) fail(where(path, 'cover_id'), 'must be null when the status is NONE')
  if (status !== 'NONE' && coverId === null) fail(where(path, 'cover_id'), 'is required when a cover exists')
  const perDay = money(r, 'premium_per_day_paise', 'premium_per_day_label', path)
  const limit = moneyOrNull(r, 'annual_limit_paise', 'annual_limit_label', path)
  const claimed = moneyOrNull(r, 'amount_claimed_paise', 'amount_claimed_label', path)
  const remaining = moneyOrNull(r, 'amount_remaining_paise', 'amount_remaining_label', path)
  return {
    merchant_id: matching(r, 'merchant_id', path, MERCHANT_ID, 'an id like S-0142'),
    cover_id: coverId,
    status,
    status_text_hi: text(r, 'status_text_hi', path),
    status_text_en: text(r, 'status_text_en', path),
    zone_id: text(r, 'zone_id', path),
    zone_name: text(r, 'zone_name', path),
    purchased_at: isoTimeOrNull(r, 'purchased_at', path),
    starts_on: isoDateOrNull(r, 'starts_on', path),
    prepaid_through: isoDateOrNull(r, 'prepaid_through', path),
    waiting_period_days: integer(r, 'waiting_period_days', path),
    premium_per_day_paise: perDay.paise,
    premium_per_day_label: perDay.label,
    premium_due: boolean(r, 'premium_due', path),
    annual_limit_paise: limit.paise,
    annual_limit_label: limit.label,
    amount_claimed_paise: claimed.paise,
    amount_claimed_label: claimed.label,
    amount_remaining_paise: remaining.paise,
    amount_remaining_label: remaining.label,
    alert_active: boolean(r, 'alert_active', path),
    alert_id: textOrNull(r, 'alert_id', path),
  }
}

const STEP_KEYS = ['name', 'status', 'result', 'at', 'reason_hi', 'reason_en', 'reason_code'] as const
const ITEM_KEYS = [
  'claim_id', 'disputed_claim_id', 'kind', 'claim_at', 'zone_id', 'trigger_id', 'decision_id', 'outcome', 'amount_paise',
  'amount_label', 'steps', 'case_id', 'case_status', 'due_by', 'resolution',
] as const

function parseStep(raw: unknown, path: string, expectedName: string): ClaimStep {
  const r = object(raw, path, STEP_KEYS)
  const name = oneOf(r, 'name', path, STEP_NAMES)
  if (name !== expectedName) fail(where(path, 'name'), `steps come in the order ${STEP_NAMES.join(', ')}`)
  const result = name === 'Decided' ? oneOfOrNull(r, 'result', path, OUTCOMES) : name === 'EDI holiday' ? oneOfOrNull(r, 'result', path, EDI_RESULTS) : null
  if (name !== 'Decided' && name !== 'EDI holiday' && r.result !== null) fail(where(path, 'result'), `must be null on the ${name} step`)
  const code = oneOfOrNull(r, 'reason_code', path, LENDER_REASON_CODES)
  if (code !== null && !(name === 'EDI holiday' && result === 'REFUSED')) fail(where(path, 'reason_code'), 'is set only when the lender refuses')
  return {
    name,
    status: oneOf(r, 'status', path, STEP_STATUSES),
    result,
    at: isoTimeOrNull(r, 'at', path),
    reason_hi: textOrNull(r, 'reason_hi', path),
    reason_en: textOrNull(r, 'reason_en', path),
    reason_code: code,
  }
}

function parseClaimItem(raw: unknown, path: string): ClaimItem {
  const r = object(raw, path, ITEM_KEYS)
  const kind = oneOf(r, 'kind', path, CLAIM_KINDS)
  const claimId = matchingOrNull(r, 'claim_id', path, CLAIM_ID, 'an id like CL-000142')
  const disputed = matchingOrNull(r, 'disputed_claim_id', path, CLAIM_ID, 'an id like CL-000142')
  const triggerId = textOrNull(r, 'trigger_id', path)
  const outcome = oneOfOrNull(r, 'outcome', path, OUTCOMES)
  const caseId = textOrNull(r, 'case_id', path)
  const caseStatus = oneOfOrNull(r, 'case_status', path, CASE_STATUSES)
  const stepsRaw = list(r.steps, where(path, 'steps'))
  if (kind === 'DISPUTE') {
    if (stepsRaw.length > 0) fail(where(path, 'steps'), 'a DISPUTE item has no steps')
    if (claimId !== null) fail(where(path, 'claim_id'), 'a DISPUTE item carries disputed_claim_id instead')
    if (disputed === null) fail(where(path, 'disputed_claim_id'), 'a DISPUTE item names the claim it is about')
    if (triggerId !== null) fail(where(path, 'trigger_id'), 'is null on a DISPUTE item')
    if (caseId === null) fail(where(path, 'case_id'), 'a DISPUTE item has a case')
  } else {
    if (claimId === null) fail(where(path, 'claim_id'), `a ${kind} claim has a claim id`)
    if (disputed !== null) fail(where(path, 'disputed_claim_id'), 'is null unless the item is a DISPUTE')
    if (stepsRaw.length !== STEP_NAMES.length) fail(where(path, 'steps'), `a claim has the five steps ${STEP_NAMES.join(', ')}`)
    if (kind === 'AREA' && triggerId === null) fail(where(path, 'trigger_id'), 'an AREA claim names its trigger')
    if (kind === 'PERSONAL' && triggerId !== null) fail(where(path, 'trigger_id'), 'is null on a PERSONAL claim')
  }
  if (kind === 'AREA' && outcome === 'REFERRED') fail(path, 'an AREA claim can never be REFERRED (area claims carry HARD checks only)')
  if (outcome === 'REFERRED' && caseId === null) fail(where(path, 'case_id'), 'a REFERRED claim has a case')
  if (caseId === null && caseStatus !== null) fail(where(path, 'case_status'), 'is null when there is no case')
  const amount = moneyOrNull(r, 'amount_paise', 'amount_label', path)
  if ((outcome === null) !== (amount.paise === null)) fail(where(path, 'amount_label'), 'an amount comes with an outcome, and only then')
  return {
    claim_id: claimId,
    disputed_claim_id: disputed,
    kind,
    claim_at: isoTime(r, 'claim_at', path),
    zone_id: textOrNull(r, 'zone_id', path),
    trigger_id: triggerId,
    decision_id: matchingOrNull(r, 'decision_id', path, DECISION_ID, 'an id like D-000142'),
    outcome,
    amount_paise: amount.paise,
    amount_label: amount.label,
    steps: stepsRaw.map((step, index) => parseStep(step, `${path}.steps[${index}]`, STEP_NAMES[index])),
    case_id: caseId,
    case_status: caseStatus,
    due_by: isoTimeOrNull(r, 'due_by', path),
    resolution: textOrNull(r, 'resolution', path),
  }
}

/** GET /api/merchants/{id}/claims: the list of items, newest first. */
export function parseClaims(raw: unknown): ClaimItem[] {
  return list(raw, 'claims').map((item, index) => parseClaimItem(item, `claims[${index}]`))
}

const SOURCE_KEYS = ['kind', 'label', 'ref', 'as_of', 'origin', 'clause'] as const

/** The closed Source object (H13): exactly six fields. */
export function parseSource(raw: unknown, path: string): Source {
  const r = object(raw, path, SOURCE_KEYS)
  return {
    kind: oneOf(r, 'kind', path, SOURCE_KINDS),
    label: text(r, 'label', path),
    ref: matching(r, 'ref', path, /^\S+$/, 'the exact record or key'),
    as_of: isoTimeOrNull(r, 'as_of', path),
    origin: oneOf(r, 'origin', path, ORIGINS),
    clause: textOrNull(r, 'clause', path),
  }
}

function parseSources(raw: unknown, path: string, required: boolean): Source[] {
  const sources = list(raw, path).map((source, index) => parseSource(source, `${path}[${index}]`))
  if (required && sources.length === 0) fail(path, 'a number or a check without a source is a contract error')
  return sources
}

function parseFact(raw: unknown, path: string): ReceiptFact {
  const r = object(raw, path, ['key', 'label_en', 'value', 'sources'])
  return { key: text(r, 'key', path), label_en: text(r, 'label_en', path), value: text(r, 'value', path), sources: parseSources(r.sources, where(path, 'sources'), true) }
}

const CHECK_KEYS = ['code', 'severity', 'status', 'label_en', 'detail_en', 'observed', 'required', 'clause', 'erased', 'sources'] as const

function parseCheck(raw: unknown, path: string): ReceiptCheck {
  const r = object(raw, path, CHECK_KEYS)
  return {
    code: text(r, 'code', path),
    severity: oneOf(r, 'severity', path, SEVERITIES),
    status: oneOf(r, 'status', path, CHECK_STATUSES),
    label_en: text(r, 'label_en', path),
    detail_en: text(r, 'detail_en', path),
    observed: textOrNull(r, 'observed', path),
    required: textOrNull(r, 'required', path),
    clause: textOrNull(r, 'clause', path),
    erased: boolean(r, 'erased', path),
    sources: parseSources(r.sources, where(path, 'sources'), true),
  }
}

const COUNTERFACTUAL_KEYS = ['id', 'kind', 'actionable', 'changes', 'result', 'verified', 'text_en', 'text_hi', 'sources'] as const

function parseCounterfactual(raw: unknown, path: string): Counterfactual {
  const r = object(raw, path, COUNTERFACTUAL_KEYS)
  if (r.verified !== true) fail(where(path, 'verified'), 'must be true: the engine never shows a counterfactual it did not re-run')
  const result =
    r.result === null
      ? null
      : (() => {
          const resultPath = where(path, 'result')
          const rr = object(r.result, resultPath, ['outcome', 'amount_paise', 'amount_label'])
          const amount = money(rr, 'amount_paise', 'amount_label', resultPath)
          return { outcome: oneOf(rr, 'outcome', resultPath, OUTCOMES), amount_paise: amount.paise, amount_label: amount.label }
        })()
  return {
    id: text(r, 'id', path),
    kind: oneOf(r, 'kind', path, COUNTERFACTUAL_KINDS),
    actionable: boolean(r, 'actionable', path),
    changes: list(r.changes, where(path, 'changes')).map((change, index) => {
      const changePath = `${path}.changes[${index}]`
      const cr = object(change, changePath, ['check_code', 'field', 'observed', 'needed'])
      return { check_code: textOrNull(cr, 'check_code', changePath), field: text(cr, 'field', changePath), observed: text(cr, 'observed', changePath), needed: text(cr, 'needed', changePath) }
    }),
    result,
    verified: true,
    text_en: text(r, 'text_en', path),
    text_hi: text(r, 'text_hi', path),
    sources: parseSources(r.sources, where(path, 'sources'), false),
  }
}

function parseEdi(raw: unknown, path: string): ReceiptEdi {
  const r = object(raw, path, ['request_id', 'status', 'reason_code', 'instalment_date', 'instalment_label', 'decided_at', 'lender'])
  const status = oneOf(r, 'status', path, HOLIDAY_STATUSES)
  const code = oneOfOrNull(r, 'reason_code', path, LENDER_REASON_CODES)
  if ((status === 'REFUSED') !== (code !== null)) fail(where(path, 'reason_code'), 'is set when the lender refuses, and in no other case')
  return {
    request_id: text(r, 'request_id', path),
    status,
    reason_code: code,
    instalment_date: isoDate(r, 'instalment_date', path),
    instalment_label: text(r, 'instalment_label', path),
    decided_at: isoTimeOrNull(r, 'decided_at', path),
    lender: text(r, 'lender', path),
  }
}

function parseReceiptDecision(raw: unknown): Receipt['decision'] {
  const path = 'receipt.decision'
  const r = object(raw, path, ['id', 'claim_id', 'merchant_id', 'outcome', 'amount_paise', 'amount_label', 'rules_version', 'decided_at', 'decided_by', 'supersedes', 'referral_reason'])
  const amount = money(r, 'amount_paise', 'amount_label', path)
  return {
    id: matching(r, 'id', path, DECISION_ID, 'an id like D-000142'),
    claim_id: matching(r, 'claim_id', path, CLAIM_ID, 'an id like CL-000142'),
    merchant_id: matching(r, 'merchant_id', path, MERCHANT_ID, 'an id like S-0142'),
    outcome: oneOf(r, 'outcome', path, OUTCOMES),
    amount_paise: amount.paise,
    amount_label: amount.label,
    rules_version: text(r, 'rules_version', path),
    decided_at: isoTime(r, 'decided_at', path),
    decided_by: text(r, 'decided_by', path),
    supersedes: matchingOrNull(r, 'supersedes', path, DECISION_ID, 'an id like D-000142'),
    referral_reason: textOrNull(r, 'referral_reason', path),
  }
}

const RECEIPT_KEYS = ['decision', 'explanation', 'checks', 'counterfactuals', 'payout', 'edi', 'case', 'audit', 'grievance'] as const

/** GET /api/decisions/{decision_id}/receipt. */
export function parseReceipt(raw: unknown): Receipt {
  const path = 'receipt'
  const r = object(raw, path, RECEIPT_KEYS)
  const explanation = object(r.explanation, 'receipt.explanation', ['formula_en', 'formula_hi', 'clause', 'facts'])
  const payout = r.payout === null ? null : object(r.payout, 'receipt.payout', ['id', 'status', 'amount_label', 'credited_at'])
  const kase = r.case === null ? null : object(r.case, 'receipt.case', ['id', 'kind', 'status', 'due_by'])
  const audit = object(r.audit, 'receipt.audit', ['seq', 'hash_short', 'verify_path'])
  const grievance = object(r.grievance, 'receipt.grievance', ['dispute_allowed', 'ladder', 'first_step_hours'])
  return {
    decision: parseReceiptDecision(r.decision),
    explanation: {
      formula_en: text(explanation, 'formula_en', 'receipt.explanation'),
      formula_hi: text(explanation, 'formula_hi', 'receipt.explanation'),
      clause: text(explanation, 'clause', 'receipt.explanation'),
      facts: list(explanation.facts, 'receipt.explanation.facts').map((fact, index) => parseFact(fact, `receipt.explanation.facts[${index}]`)),
    },
    checks: list(r.checks, 'receipt.checks').map((check, index) => parseCheck(check, `receipt.checks[${index}]`)),
    counterfactuals: list(r.counterfactuals, 'receipt.counterfactuals').map((cf, index) => parseCounterfactual(cf, `receipt.counterfactuals[${index}]`)),
    payout:
      payout === null
        ? null
        : {
            id: text(payout, 'id', 'receipt.payout'),
            status: oneOf(payout, 'status', 'receipt.payout', PAYOUT_STATUSES),
            amount_label: text(payout, 'amount_label', 'receipt.payout'),
            credited_at: isoTimeOrNull(payout, 'credited_at', 'receipt.payout'),
          },
    edi: r.edi === null ? null : parseEdi(r.edi, 'receipt.edi'),
    case:
      kase === null
        ? null
        : {
            id: text(kase, 'id', 'receipt.case'),
            kind: oneOf(kase, 'kind', 'receipt.case', CASE_KINDS),
            status: oneOf(kase, 'status', 'receipt.case', CASE_STATUSES),
            due_by: isoTime(kase, 'due_by', 'receipt.case'),
          },
    audit: {
      seq: integer(audit, 'seq', 'receipt.audit'),
      hash_short: matching(audit, 'hash_short', 'receipt.audit', HASH_PREFIX, '12 hex characters'),
      verify_path: text(audit, 'verify_path', 'receipt.audit'),
    },
    grievance: {
      dispute_allowed: boolean(grievance, 'dispute_allowed', 'receipt.grievance'),
      ladder: list(grievance.ladder, 'receipt.grievance.ladder').map((step, index) =>
        typeof step === 'string' && step !== '' ? step : fail(`receipt.grievance.ladder[${index}]`, 'expected a step id'),
      ),
      first_step_hours: integer(grievance, 'first_step_hours', 'receipt.grievance'),
    },
  }
}

const QUOTE_KEYS = [
  'id', 'merchant_id', 'outcome', 'requested_at', 'starts_on', 'premium_per_day_paise', 'premium_per_day_label', 'first_payment_paise',
  'first_payment_label', 'days_prepaid', 'reason_en', 'reason_hi', 'blocking_alert_id',
] as const
const PREMIUM_KEYS = [
  'id', 'merchant_id', 'amount_paise', 'amount_label', 'method', 'covers_from', 'covers_to', 'status', 'link_id', 'link_url', 'source',
  'created_at', 'paid_at',
] as const

function parseQuote(raw: unknown, path: string): CoverQuote {
  const r = object(raw, path, QUOTE_KEYS)
  const perDay = money(r, 'premium_per_day_paise', 'premium_per_day_label', path)
  const first = money(r, 'first_payment_paise', 'first_payment_label', path)
  return {
    id: text(r, 'id', path),
    merchant_id: matching(r, 'merchant_id', path, MERCHANT_ID, 'an id like S-0142'),
    outcome: oneOf(r, 'outcome', path, QUOTE_OUTCOMES),
    requested_at: isoTime(r, 'requested_at', path),
    starts_on: isoDate(r, 'starts_on', path),
    premium_per_day_paise: perDay.paise,
    premium_per_day_label: perDay.label,
    first_payment_paise: first.paise,
    first_payment_label: first.label,
    days_prepaid: integer(r, 'days_prepaid', path),
    reason_en: text(r, 'reason_en', path),
    reason_hi: text(r, 'reason_hi', path),
    blocking_alert_id: textOrNull(r, 'blocking_alert_id', path),
  }
}

function parsePremium(raw: unknown, path: string): PremiumPayment {
  const r = object(raw, path, PREMIUM_KEYS)
  const amount = money(r, 'amount_paise', 'amount_label', path)
  return {
    id: text(r, 'id', path),
    merchant_id: matching(r, 'merchant_id', path, MERCHANT_ID, 'an id like S-0142'),
    amount_paise: amount.paise,
    amount_label: amount.label,
    method: oneOf(r, 'method', path, PREMIUM_METHODS),
    covers_from: isoDate(r, 'covers_from', path),
    covers_to: isoDate(r, 'covers_to', path),
    status: oneOf(r, 'status', path, PREMIUM_STATUSES),
    link_id: textOrNull(r, 'link_id', path),
    link_url: textOrNull(r, 'link_url', path),
    source: text(r, 'source', path),
    created_at: isoTime(r, 'created_at', path),
    paid_at: isoTimeOrNull(r, 'paid_at', path),
  }
}

/** POST /api/premium/link: a quote (OK or BLOCKED, never "approved") and, when a link was made, the payment. */
export function parsePremiumLink(raw: unknown): PremiumLinkResult {
  const r = object(raw, 'premium_link', ['quote', 'premium'])
  return { quote: parseQuote(r.quote, 'premium_link.quote'), premium: r.premium === null ? null : parsePremium(r.premium, 'premium_link.premium') }
}
