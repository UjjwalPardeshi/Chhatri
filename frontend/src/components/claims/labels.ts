/** Display labels for cases and checks (SPEC §9.2, §12). */
import type { CaseKind, CaseStatus, CheckStatus } from '../../api/types'

export const CASE_KIND_LABELS: Readonly<Record<CaseKind, string>> = Object.freeze({
  PERSONAL_CLAIM_REVIEW: 'Personal claim review',
  DISPUTE: 'Dispute',
  AREA_REVIEW: 'Area review',
})

export const CASE_STATUS_TONES: Readonly<Record<CaseStatus, string>> = Object.freeze({
  OPEN: 'amber',
  APPROVED: 'green',
  DECLINED: 'red',
  CLOSED: 'grey',
})

export const CHECK_STATUS: Readonly<Record<CheckStatus, { label: string; tone: string; icon: 'check' | 'cross' | 'question' | 'dash' | 'shield' }>> = Object.freeze({
  PASS: { label: 'Pass', tone: 'green', icon: 'check' },
  FAIL: { label: 'Fail', tone: 'red', icon: 'cross' },
  UNSURE: { label: 'Unsure', tone: 'amber', icon: 'question' },
  NOT_APPLICABLE: { label: 'N/A', tone: 'grey', icon: 'dash' },
  WAIVED_BY_OFFICER: { label: 'Waived by officer', tone: 'amber', icon: 'shield' },
})

export const OUTCOME_TONES: Readonly<Record<string, string>> = Object.freeze({ APPROVED: 'green', REFERRED: 'amber', DECLINED: 'red' })

export const NAME_SCORE_MIN = 85
