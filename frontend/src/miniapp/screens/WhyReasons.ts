/**
 * The plain-words reason a decision has no amount (fs-04 S6, copy deck 3.2 and 13): for a decision that went to a
 * person, the SOFT checks that failed or were unsure, each as its `TRACK_REFERRED_*` line; for a declined one, the
 * HARD checks that failed, each as its built `REASON_*` line, or the officer's line when a person declined it. A
 * check with no line here adds none: the engine's own labels are on the receipt.
 */
import type { Receipt, ReceiptCheck } from '../../api/types'
import type { CopyKey } from '../lib/copy'

const REFERRED_LINES: Readonly<Record<string, CopyKey>> = {
  SLIP_READABLE: 'TRACK_REFERRED_UNREADABLE',
  NAME_MATCHES_KYC: 'TRACK_REFERRED_NAME',
  DATES_MATCH: 'TRACK_REFERRED_DATES',
  WITHIN_AUTO_LIMIT: 'TRACK_REFERRED_DAYS',
}

const DECLINED_LINES: Readonly<Record<string, CopyKey>> = {
  COVER_IN_FORCE: 'REASON_COVER_IN_FORCE',
  PREMIUM_PREPAID: 'REASON_PREMIUM_PREPAID',
  SILENCE_VERIFIED: 'REASON_SILENCE_VERIFIED',
  NOT_ALREADY_PAID: 'REASON_NOT_ALREADY_PAID',
  WITHIN_ANNUAL_LIMIT: 'REASON_WITHIN_ANNUAL_LIMIT',
  COVER_BEFORE_ALERT: 'REASON_COVER_BEFORE_ALERT',
  ALERT_ACTIVE: 'REASON_ALERT_ACTIVE',
  INDEX_QUORUM: 'REASON_INDEX_QUORUM',
  BELOW_FLOOR: 'REASON_BELOW_FLOOR',
  BELOW_MODEL_RANGE: 'REASON_BELOW_MODEL_RANGE',
}

const doubtful = (check: ReceiptCheck): boolean => check.status === 'FAIL' || check.status === 'UNSURE'
const lineOf = (lines: Readonly<Record<string, CopyKey>>, code: string): CopyKey | null => (Object.hasOwn(lines, code) ? lines[code] : null)

export function reasonKeys(receipt: Receipt): CopyKey[] {
  const { outcome, decided_by: by } = receipt.decision
  if (outcome === 'REFERRED') {
    return receipt.checks.filter((check) => check.severity === 'SOFT' && doubtful(check)).flatMap((check) => lineOf(REFERRED_LINES, check.code) ?? [])
  }
  if (outcome !== 'DECLINED') return []
  const failed = receipt.checks.filter((check) => check.severity === 'HARD' && check.status === 'FAIL').flatMap((check) => lineOf(DECLINED_LINES, check.code) ?? [])
  return failed.length > 0 || !by.startsWith('officer:') ? failed : ['REASON_OFFICER_PERSONAL']
}
