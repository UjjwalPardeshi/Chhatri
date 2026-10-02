/**
 * Decisions and the payout workflow for the mock (SPEC §4.3, §9.2–9.6, §10; decisions B1/B2):
 * execute_payout +0 (PENDING), credit_payout +4 (CREDITED), notify_merchant +4, request_holiday +5,
 * all on simulated time from the decision. Amounts follow the published-numbers rule. The last step is
 * the lender's decision when x4_lender_request is on (grants by default, no answer when forced) and the
 * BUILT unconditional pause when it is off.
 */
import type { Check, CheckStatus, Decision, DecisionOutcome, Explanation, InstalmentPause, Payout, Severity } from '../api/types'
import { isFeatureEnabled } from '../features'
import { formatInr } from '../lib/money'
import { HOLIDAY, MSG, WEEKDAYS_EN, WEEKDAYS_HI, type Bilingual } from './catalogue'
import { LENDER_NAME, PAYOUT_RAIL, RULES_VERSION, type MockMerchant } from './fixtures'
import type { MockHolidayRequest, MockRuntime } from './runtime'
import { addDays, weekdayIndex } from './scenarios'

export const PAYOUT_SHARE_PCT = 50
export const AREA_DAILY_CAP_PAISE = 250_000
export const PERSONAL_DAILY_CAP_PAISE = 150_000
export const PAYOUT_RAIL_DELAY_MIN = 4
export const INSTALMENT_PAUSE_DELAY_MIN = 5
const PAISE_PER_RUPEE = 100
/** The flag that makes the lender decide the EDI holiday (X4). */
export const LENDER_FLAG = 'x4_lender_request'
const WORKFLOW_ACTOR = 'workflow:payout'
const MOVED_TO_END_OF_TENURE = 'end of tenure'

export function roundToRupee(paise: number): number {
  return Math.floor(paise / PAISE_PER_RUPEE + 0.5) * PAISE_PER_RUPEE
}

export function check(code: string, severity: Severity, status: CheckStatus, label: string, observed: string | null = null, required: string | null = null, detail = ''): Check {
  return { code, severity, status, label_en: label, detail_en: detail || label, observed, required }
}

export function areaExplanation(day: string, expectedPaise: number, dropPct: number): Explanation {
  const raw = (expectedPaise * PAYOUT_SHARE_PCT * dropPct) / (100 * 100)
  const computed = roundToRupee(raw)
  const amount = Math.min(computed, AREA_DAILY_CAP_PAISE)
  const capped = computed > AREA_DAILY_CAP_PAISE
  const expected = formatInr(expectedPaise)
  const lost = Math.round((expectedPaise * dropPct) / 100)
  const capEn = capped ? `, capped at ${formatInr(AREA_DAILY_CAP_PAISE)}` : ''
  const capHi = capped ? `; सीमा ${formatInr(AREA_DAILY_CAP_PAISE)}` : ''
  const wd = weekdayIndex(day)
  return {
    weekday_en: WEEKDAYS_EN[wd],
    weekday_hi: WEEKDAYS_HI[wd],
    expected_day_paise: expectedPaise,
    expected_day_label: expected,
    drop_pct: dropPct,
    share_pct: PAYOUT_SHARE_PCT,
    days: 1,
    cap_paise: AREA_DAILY_CAP_PAISE,
    capped,
    amount_paise: amount,
    amount_label: formatInr(amount),
    formula_en: `½ × ${expected} × ${dropPct}% = ${formatInr(computed)}${capEn}`,
    formula_hi: `${expected} का ${dropPct}% = ${formatInr(lost)}; उसका आधा = ${formatInr(computed)}${capHi}`,
  }
}

export function personalExplanation(day: string, expectedPaise: number, days: number): Explanation {
  const half = roundToRupee((expectedPaise * PAYOUT_SHARE_PCT) / 100)
  const perDay = Math.min(half, PERSONAL_DAILY_CAP_PAISE)
  const capped = half > PERSONAL_DAILY_CAP_PAISE
  const amount = perDay * days
  const dayWord = days === 1 ? 'day' : 'days'
  const expected = formatInr(expectedPaise)
  const wd = weekdayIndex(day)
  const formulaEn = capped
    ? `½ × ${expected} = ${formatInr(half)} a day, capped at ${formatInr(perDay)} × ${days} ${dayWord} = ${formatInr(amount)}`
    : `½ × ${expected} = ${formatInr(half)} a day × ${days} ${dayWord} = ${formatInr(amount)}`
  const formulaHi = capped
    ? `${expected} का आधा = ${formatInr(half)} प्रतिदिन; सीमा ${formatInr(perDay)} × ${days} दिन = ${formatInr(amount)}`
    : `${expected} का आधा = ${formatInr(half)} प्रतिदिन × ${days} दिन = ${formatInr(amount)}`
  return {
    weekday_en: WEEKDAYS_EN[wd],
    weekday_hi: WEEKDAYS_HI[wd],
    expected_day_paise: expectedPaise,
    expected_day_label: expected,
    drop_pct: null,
    share_pct: PAYOUT_SHARE_PCT,
    days,
    cap_paise: PERSONAL_DAILY_CAP_PAISE,
    capped,
    amount_paise: amount,
    amount_label: formatInr(amount),
    formula_en: formulaEn,
    formula_hi: formulaHi,
  }
}

/** SPEC §9.3: any HARD fail ⇒ DECLINED; any SOFT fail/unsure ⇒ REFERRED; else APPROVED. */
export function outcomeOf(checks: readonly Check[]): DecisionOutcome {
  if (checks.some((c) => c.severity === 'HARD' && c.status === 'FAIL')) return 'DECLINED'
  if (checks.some((c) => c.severity === 'SOFT' && (c.status === 'FAIL' || c.status === 'UNSURE'))) return 'REFERRED'
  return 'APPROVED'
}

type DecisionInput = { claimId: string; merchantId: string; checks: Check[]; explanation: Explanation; decidedBy: string; referral: string | null; supersedes?: string | null }

export function decide(rt: MockRuntime, input: DecisionInput): Decision {
  const outcome = outcomeOf(input.checks)
  const amount = outcome === 'DECLINED' ? 0 : input.explanation.amount_paise
  const decision: Decision = {
    id: rt.nextId('D'),
    claim_id: input.claimId,
    merchant_id: input.merchantId,
    outcome,
    amount_paise: amount,
    amount_label: formatInr(amount),
    checks: input.checks,
    rules_version: RULES_VERSION,
    decided_at: rt.nowIso,
    decided_by: input.decidedBy,
    explanation: input.explanation,
    referral_reason: outcome === 'REFERRED' ? input.referral : null,
    supersedes: input.supersedes ?? null,
  }
  rt.decisions.push(decision)
  rt.emit('decision', { decision })
  rt.record(input.decidedBy, 'decision.made', 'decision', decision.id, { outcome, amount_paise: amount, checks: input.checks.map((c) => [c.code, c.status]) })
  return decision
}

export type PaidHooks = {
  onCredited: (payout: Payout) => void
  /** An instalment was paused: `text` is the merchant's line, in the lender's words while x4_lender_request is on. */
  onPaused: (text: Bilingual) => void
}

/** Schedules the B1 payout workflow for an APPROVED decision made at the current minute. */
export function schedulePayout(rt: MockRuntime, decision: Decision, merchant: MockMerchant, hooks: PaidHooks): void {
  const decidedMin = rt.minute
  let payout: Payout | null = null
  rt.schedule(decidedMin, 'execute_payout', () => {
    payout = { id: rt.nextId('P'), decision_id: decision.id, merchant_id: merchant.id, amount_paise: decision.amount_paise, amount_label: decision.amount_label, status: 'PENDING', rail: PAYOUT_RAIL, created_at: rt.nowIso, credited_at: null, reference: `SIM-${decision.id}` }
    rt.payouts.push(payout)
    rt.emit('payout', { payout })
    rt.record('workflow:payout', 'payout.executed', 'payout', payout.id, { amount_paise: payout.amount_paise })
  })
  rt.schedule(decidedMin + PAYOUT_RAIL_DELAY_MIN, 'credit_payout', () => {
    if (!payout) throw new Error(`credit_payout before execute_payout for ${decision.id}`)
    const credited: Payout = { ...payout, status: 'CREDITED', credited_at: rt.nowIso }
    rt.payouts = rt.payouts.map((p) => (p.id === credited.id ? credited : p))
    rt.emit('payout', { payout: credited })
    rt.record('workflow:payout', 'payout.credited', 'payout', credited.id, { amount_paise: credited.amount_paise })
    hooks.onCredited(credited)
  })
  if (merchant.instalment_paise === null) return
  rt.schedule(decidedMin + INSTALMENT_PAUSE_DELAY_MIN, 'request_holiday', () => requestHoliday(rt, decision, merchant, hooks))
}

/** The loan id the backend gives a merchant's loan (S-0142 has LN-0142). */
function loanIdOf(merchant: MockMerchant): string {
  return `LN-${merchant.id.slice(2)}`
}

/**
 * How many of `requested` holiday requests end as a paused instalment. The lender grants every one by default;
 * while it is forced to FALLBACK (flag on) it answers none, and an unanswered request pauses nothing (fs-03 section 7).
 */
export function holidaysGranted(rt: MockRuntime, requested: number): number {
  return isFeatureEnabled(LENDER_FLAG) && rt.lenderForced ? 0 : requested
}

/** The step after the credit: the lender decides (flag on), or the BUILT pause that never asks (flag off). */
function requestHoliday(rt: MockRuntime, decision: Decision, merchant: MockMerchant, hooks: PaidHooks): void {
  if (isFeatureEnabled(LENDER_FLAG)) askLender(rt, decision, merchant, hooks)
  else pauseInstalment(rt, decision, merchant, hooks)
}

function openPause(rt: MockRuntime, decision: Decision, merchant: MockMerchant, reason: string, requestId: string | null): InstalmentPause {
  const amount = merchant.instalment_paise ?? 0
  const pause: InstalmentPause = {
    id: rt.nextId('IP'),
    loan_id: loanIdOf(merchant),
    merchant_id: merchant.id,
    instalment_date: addDays(rt.scenario.day, 1),
    amount_paise: amount,
    amount_label: formatInr(amount),
    reason,
    decision_id: decision.id,
    created_at: rt.nowIso,
  }
  rt.pauses.push(pause)
  rt.emit('instalment', { pause })
  const via = requestId === null ? {} : { request_id: requestId }
  rt.record(WORKFLOW_ACTOR, 'instalment.pause', 'instalment_pause', pause.id, { amount_paise: amount, instalment_date: pause.instalment_date, ...via })
  return pause
}

/** The BUILT step: pause at once and say it is paused (x4_lender_request off). */
function pauseInstalment(rt: MockRuntime, decision: Decision, merchant: MockMerchant, hooks: PaidHooks): void {
  const reason = `Paused by Chhatri after ${decision.id}; moved to the end of the tenure (${LENDER_NAME})`
  const pause = openPause(rt, decision, merchant, reason, null)
  hooks.onPaused(MSG.instalmentPaused(pause.amount_label))
}

/** The lender's side of the request (the simulated lender, ADR 0006): grants unless it is forced to give no answer. */
function answerOf(rt: MockRuntime, request: MockHolidayRequest): MockHolidayRequest {
  const status = rt.lenderForced ? 'NO_RESPONSE' : 'GRANTED'
  return { ...request, status, reason_code: null, decided_at: rt.nowIso }
}

function auditRequest(rt: MockRuntime, request: MockHolidayRequest): void {
  rt.record(WORKFLOW_ACTOR, 'instalment.holiday_request', 'holiday_request', request.id, {
    merchant_id: request.merchant_id,
    loan_id: request.loan_id,
    decision_id: request.decision_id,
    payout_id: request.payout_id,
    instalment_date: request.instalment_date,
    amount_paise: request.instalment_paise,
    lender: request.lender,
  })
}

function auditAnswer(rt: MockRuntime, answered: MockHolidayRequest): void {
  const granted = answered.status === 'GRANTED'
  rt.record(WORKFLOW_ACTOR, 'instalment.holiday_decision', 'holiday_request', answered.id, {
    merchant_id: answered.merchant_id,
    loan_id: answered.loan_id,
    decision: answered.status,
    reason_code: answered.reason_code,
    moved_to: granted ? MOVED_TO_END_OF_TENURE : null,
    penalty_paise: 0,
    lender: answered.lender,
  })
}

/** X4: Chhatri only asks, once, after the payout is credited; the lender's answer is what the merchant is told. */
function askLender(rt: MockRuntime, decision: Decision, merchant: MockMerchant, hooks: PaidHooks): void {
  const payout = rt.payouts.find((p) => p.decision_id === decision.id)
  if (payout?.status !== 'CREDITED') {
    rt.record(WORKFLOW_ACTOR, 'instalment.holiday_skipped', 'decision', decision.id, { merchant_id: merchant.id, decision_id: decision.id, reason: 'PAYOUT_NOT_CREDITED', payout_status: payout?.status ?? null })
    return
  }
  const amount = merchant.instalment_paise ?? 0
  const asked: MockHolidayRequest = {
    id: rt.nextId('HR'),
    loan_id: loanIdOf(merchant),
    merchant_id: merchant.id,
    decision_id: decision.id,
    payout_id: payout.id,
    instalment_date: addDays(rt.scenario.day, 1),
    instalment_paise: amount,
    instalment_label: formatInr(amount),
    requested_at: rt.nowIso,
    status: 'REQUESTED',
    reason_code: null,
    decided_at: null,
    lender: LENDER_NAME,
  }
  rt.holidayRequests = [...rt.holidayRequests, asked]
  auditRequest(rt, asked)
  const answered = answerOf(rt, asked)
  rt.holidayRequests = rt.holidayRequests.map((r) => (r.id === answered.id ? answered : r))
  auditAnswer(rt, answered)
  if (answered.status === 'GRANTED') {
    const reason = `Lender granted holiday ${answered.id} after Chhatri payout ${decision.id}; moved to the end of the tenure, no penalty (${LENDER_NAME})`
    openPause(rt, decision, merchant, reason, answered.id)
    hooks.onPaused(HOLIDAY.granted(answered.instalment_label, 'tomorrow'))
    return
  }
  rt.send(merchant.id, { kind: 'TEXT', text: HOLIDAY.noResponse(answered.instalment_label, 'tomorrow') })
}
