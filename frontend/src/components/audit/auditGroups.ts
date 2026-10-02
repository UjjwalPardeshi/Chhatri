/**
 * Audit rows for reading (SPEC §11 audit log, §20 "Audit"): entries grouped by simulated minute
 * (newest first, as shown), and which actions move money, so those rows can be marked.
 */
import type { AuditEntry } from '../../api/types'
import { dayLabel, hhmm } from '../../lib/time'

export type AuditGroup = { key: string; label: string; items: AuditEntry[] }

/**
 * Actions that move money or a loan instalment: payout.executed, payout.credited and instalment.pause. Asking the
 * lender for a holiday and its answer (instalment.holiday_request, instalment.holiday_decision) move nothing:
 * only a grant ends in a pause.
 */
const MONEY_ACTION = /^(payout\..+|instalment\.pause)$/

export function isMoneyAction(action: string): boolean {
  return MONEY_ACTION.test(action)
}

const ACTION_NAMES: Readonly<Record<string, string>> = Object.freeze({
  'instalment.holiday_request': 'Lender asked',
  'instalment.holiday_decision': 'Lender answered',
})

/**
 * A plain name for the two audit actions of the EDI holiday (X4), shown beside the raw action; null for any other
 * action. The decision entry is also written when the lender gave no answer, and then it says so.
 */
export function actionName(entry: Pick<AuditEntry, 'action' | 'data'>): string | null {
  if (entry.action === 'instalment.holiday_decision' && entry.data.decision === 'NO_RESPONSE') return 'Lender did not answer'
  return ACTION_NAMES[entry.action] ?? null
}

/** "19 Aug 2025 · 17:04" groups, in the order the entries come. */
export function groupByMinute(entries: readonly AuditEntry[]): AuditGroup[] {
  return entries.reduce<AuditGroup[]>((groups, entry) => {
    const label = `${dayLabel(entry.at)} · ${hhmm(entry.at)}`
    const last = groups.at(-1)
    if (last?.label === label) return [...groups.slice(0, -1), { ...last, items: [...last.items, entry] }]
    return [...groups, { key: `${entry.seq}`, label, items: [entry] }]
  }, [])
}
