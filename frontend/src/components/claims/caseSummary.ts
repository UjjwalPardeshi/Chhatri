/**
 * The case headline in plain words (SPEC §9.2 checks, §9.4 referral, §12 case summary): a
 * referred personal claim reads "Personal claim ₹1,500 for Anil's Tea Stall sent to a human: the
 * name on the slip doesn't match KYC." with the rule underneath in small type ("Rule
 * NAME_MATCHES_KYC failed · score 41 of 85 needed"). The server's `summary_en` stays available as
 * the headline's tooltip, and is shown as it is for disputes, area reviews and anything else.
 *
 * After an officer approval (SPEC §9.4) every SOFT check of the new decision reads
 * WAIVED_BY_OFFICER, including the ones that passed, so the reason is taken from the policy
 * engine's REFERRED decision that the officer's decision supersedes (`referral`). Without it the
 * headline falls back to the server's summary, which always names the real reason.
 */
import type { Case, Check, Decision } from '../../api/types'
import { NAME_SCORE_MIN } from './labels'

/** How a failing check reads after "sent to a human:". */
export const FAILURE_CLAUSES: Readonly<Record<string, string>> = Object.freeze({
  NAME_MATCHES_KYC: 'the name on the slip doesn’t match KYC',
  DATES_MATCH: 'the dates on the slip don’t match the silent days',
  SLIP_READABLE: 'the slip can’t be read clearly',
  HOSPITAL_IDENTIFIED: 'the hospital on the slip isn’t in the directory',
  DOCTOR_IDENTIFIED: 'the doctor on the slip isn’t on that hospital’s register',
  VERIFICATION_CONSENT: 'the merchant would rather we didn’t ask the doctor',
  DOCTOR_NOT_DENIED: 'the doctor said the patient did not attend',
  DOCTOR_CONFIRMED: 'the doctor hasn’t confirmed the visit',
})

export type CaseHeadline = { text: string; rule: string | null }

type HeadlineInput = Pick<Case, 'kind' | 'summary_en' | 'merchant_name' | 'decision' | 'evidence'>

/** The check that sent the claim to a human: the first failure, else the first unsure one. */
function blockingCheck(checks: readonly Check[]): Check | null {
  return checks.find((c) => c.status === 'FAIL') ?? checks.find((c) => c.status === 'UNSURE') ?? null
}

function ruleLine(check: Check, score: number | undefined, waived: boolean): string {
  const verb = check.status === 'UNSURE' ? 'was unsure' : 'failed'
  const detail = check.code === 'NAME_MATCHES_KYC' && score !== undefined ? `score ${score} of ${NAME_SCORE_MIN} needed` : check.observed
  const parts = [`Rule ${check.code} ${verb}`, detail, waived ? 'waived by the officer' : null]
  return parts.filter((p): p is string => Boolean(p)).join(' · ')
}

/** The decision that explains the referral: the case's own when REFERRED, else the superseded one. */
export function referralDecision(decision: Decision | null, referral: Decision | null = null): Decision | null {
  if (decision?.outcome === 'REFERRED') return decision
  return referral?.outcome === 'REFERRED' ? referral : null
}

export function caseHeadline(item: HeadlineInput, referral: Decision | null = null): CaseHeadline {
  const decision = item.decision
  const reason = item.kind === 'PERSONAL_CLAIM_REVIEW' ? referralDecision(decision, referral) : null
  const check = reason ? blockingCheck(reason.checks) : null
  if (!decision || !check) return { text: item.summary_en, rule: null }
  const clause = FAILURE_CLAUSES[check.code] ?? `the check “${check.label_en}” did not pass`
  const waived = decision.id !== reason?.id && decision.outcome === 'APPROVED'
  return { text: `Personal claim ${decision.amount_label} for ${item.merchant_name} sent to a human: ${clause}.`, rule: ruleLine(check, item.evidence.name_score, waived) }
}
