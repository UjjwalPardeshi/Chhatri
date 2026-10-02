/**
 * Pure helpers that read the decision receipt for the case panel (fs-08 section 8, card 6.1): the sources of each
 * check (H13) as chip text, and the dispute wording (K5). A chip says where a value came from. It never says that an
 * outside body verified it, because every input is SIMULATED today (data-model 5.8).
 */
import type { Receipt, Source } from '../../api/types'
import { dayLabel, hhmm } from '../../lib/time'

/** The sources of every check of a receipt, by check code. */
export function sourcesByCode(receipt: Pick<Receipt, 'checks'>): Readonly<Record<string, readonly Source[]>> {
  return Object.fromEntries(receipt.checks.map((c) => [c.code, c.sources]))
}

/** "label · record id · 18 Aug 17:30 · SIMULATED"; configuration has no time, so the time is left out. */
export function sourceChipText(source: Source): string {
  const when = source.as_of ? `${dayLabel(source.as_of).split(' ').slice(0, 2).join(' ')} ${hhmm(source.as_of)}` : null
  return [source.label, source.ref, when, source.origin].filter((part): part is string => part !== null).join(' · ')
}

/** console.dispute.* of the copy deck. The routes stay /approve and /decline. */
export const DISPUTE_COPY = Object.freeze({
  confirm: 'Confirm payout',
  reject: 'Reject dispute',
  hint: 'The amount cannot change. Confirming keeps the payout. Rejecting closes the dispute. The merchant is told the result either way.',
})

/** console.cf.note of the copy deck. */
export const COUNTERFACTUAL_NOTE = 'checked by re-running the engine'
