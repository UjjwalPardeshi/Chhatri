/**
 * Audit rows for reading (SPEC §11 audit log, §20 "Audit"): entries grouped by simulated minute
 * (newest first, as shown), and which actions move money, so those rows can be marked.
 */
import type { AuditEntry } from '../../api/types'
import { dayLabel, hhmm } from '../../lib/time'

export type AuditGroup = { key: string; label: string; items: AuditEntry[] }

/** Actions that move money or a loan instalment (payout.executed, payout.credited, instalment.paused …). */
const MONEY_ACTION = /^(payout|instalment)\./

export function isMoneyAction(action: string): boolean {
  return MONEY_ACTION.test(action)
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
