/**
 * "Why a human" in plain words (SPEC §9.2 checks, §9.4 authority, §12 case evidence): the checks
 * that stopped an automatic payout, failures first, each with what was seen against what the
 * policy needs. The name check reads its numbers from the case evidence (slip name, KYC name and
 * score), so the officer sees "Slip: Sunil Pawar · KYC: ANIL RAMESH JADHAV · score 41/100, needs
 * 85" instead of the engine's code. The engine's own sentence stays available as a second line.
 */
import type { CaseEvidence, Check, CheckStatus } from '../../api/types'
import { NAME_SCORE_MIN } from './labels'

/** How a failing check reads, when its label states the passing condition. */
export const FAILURE_TITLES: Readonly<Record<string, string>> = Object.freeze({
  NAME_MATCHES_KYC: 'Name on the slip doesn’t match KYC',
  DATES_MATCH: 'Dates on the slip don’t match the silent days',
  SLIP_READABLE: 'The slip can’t be read clearly',
})

/** Display order of check results: what blocks the money first. */
export const STATUS_ORDER: Readonly<Record<CheckStatus, number>> = Object.freeze({ FAIL: 0, UNSURE: 1, WAIVED_BY_OFFICER: 2, PASS: 3, NOT_APPLICABLE: 4 })

export type HumanReason = { code: string; tone: 'red' | 'amber'; title: string; detail: string | null }

export function sortChecks(checks: readonly Check[]): Check[] {
  return checks.toSorted((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || (a.severity === b.severity ? 0 : a.severity === 'HARD' ? -1 : 1))
}

function nameDetail(evidence: CaseEvidence): string | null {
  const slipName = evidence.slip?.patient_name
  if (!slipName || !evidence.kyc_name) return null
  const score = evidence.name_score === undefined ? '' : ` · score ${evidence.name_score}/100, needs ${NAME_SCORE_MIN}`
  return `Slip: ${slipName} · KYC: ${evidence.kyc_name}${score}`
}

function genericDetail(check: Check): string | null {
  if (check.observed && check.required) return `${check.observed} · needs ${check.required}`
  return check.observed ?? check.detail_en ?? null
}

/** The checks that sent the claim to a human, failures before unsure ones. */
export function humanReasons(checks: readonly Check[], evidence: CaseEvidence): HumanReason[] {
  return sortChecks(checks)
    .filter((c) => c.status === 'FAIL' || c.status === 'UNSURE')
    .map((c) => ({
      code: c.code,
      tone: c.status === 'FAIL' ? 'red' : 'amber',
      title: c.status === 'FAIL' ? (FAILURE_TITLES[c.code] ?? c.label_en) : `Unsure: ${c.label_en}`,
      detail: (c.code === 'NAME_MATCHES_KYC' ? nameDetail(evidence) : null) ?? genericDetail(c),
    }))
}
