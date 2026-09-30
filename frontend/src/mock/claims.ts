/**
 * Decisions and the payout workflow for the mock (SPEC §4.3, §9.2–9.6, §10; decisions B1/B2):
 * execute_payout +0 (PENDING), credit_payout +4 (CREDITED), notify_merchant +4, pause_instalment +5,
 * all on simulated time from the decision. Amounts follow the published-numbers rule.
 */
import type { Check, CheckStatus, Decision, DecisionOutcome, Explanation, Payout, Severity } from '../api/types'
import { formatInr } from '../lib/money'
import { WEEKDAYS_EN, WEEKDAYS_HI } from './catalogue'
import { LENDER_NAME, PAYOUT_RAIL, RULES_VERSION, type MockMerchant } from './fixtures'
import type { MockRuntime } from './runtime'
import { addDays, weekdayIndex } from './scenarios'

export const PAYOUT_SHARE_PCT = 50
export const AREA_DAILY_CAP_PAISE = 250_000
export const PERSONAL_DAILY_CAP_PAISE = 150_000
export const PAYOUT_RAIL_DELAY_MIN = 4
export const INSTALMENT_PAUSE_DELAY_MIN = 5
const PAISE_PER_RUPEE = 100

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

export type PaidHooks = { onCredited: (payout: Payout) => void; onPaused: () => void }

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
  rt.schedule(decidedMin + INSTALMENT_PAUSE_DELAY_MIN, 'pause_instalment', () => pauseInstalment(rt, decision, merchant, hooks))
}

function pauseInstalment(rt: MockRuntime, decision: Decision, merchant: MockMerchant, hooks: PaidHooks): void {
  const amount = merchant.instalment_paise ?? 0
  const pause = {
    id: rt.nextId('IP'),
    loan_id: `L-${merchant.id.slice(2)}`,
    merchant_id: merchant.id,
    instalment_date: addDays(rt.scenario.day, 1),
    amount_paise: amount,
    amount_label: formatInr(amount),
    reason: `Paused by Chhatri after ${decision.id}; moved to the end of the tenure (${LENDER_NAME})`,
    decision_id: decision.id,
    created_at: rt.nowIso,
  }
  rt.pauses.push(pause)
  rt.emit('instalment', { pause })
  rt.record('workflow:payout', 'instalment.paused', 'instalment', pause.id, { amount_paise: amount, instalment_date: pause.instalment_date })
  hooks.onPaused()
}
