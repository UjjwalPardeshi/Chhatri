/**
 * What the receipt rows are made from (fs-04 10.2): helpers that read the receipt and decide nothing new. The sources
 * of a number are the ones the API names for it, the clauses are the ones the API names on its facts and checks, and
 * the lender's line is the fixed line for the lender's answer (never a reason code, and never "Chhatri paused").
 */
import type { CheckStatus, ClaimItem, Receipt, ReceiptCheck, ReceiptDecision, ReceiptEdi } from '../../api/types'
import type { Line } from '../hooks/trackerModel'
import { formatDate } from '../lib/format'
import type { Lang } from '../lib/lang'

/** A receipt exists once the payout is credited; before that, and for a decision with no payout, it is a record. */
export const isCredited = (receipt: Receipt): boolean => receipt.payout?.status === 'CREDITED'

/** A claims officer made this decision (`decided_by` is `officer:…`); otherwise the policy engine did. */
export const isOfficerDecision = (decision: ReceiptDecision): boolean => decision.decided_by.startsWith('officer:')

const clauseNumbers = (clause: string): number[] => clause.replace(/^C/, '').split('.').map(Number)

/** C4.1 sorts after C4 and before C10: by the numbers in the id. */
function clauseOrder(a: string, b: string): number {
  const [left, right] = [clauseNumbers(a), clauseNumbers(b)]
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const difference = (left[index] ?? -1) - (right[index] ?? -1)
    if (difference !== 0) return difference
  }
  return 0
}

/** The clauses the receipt names, once each: on the amount, on each fact and source, and on each check. */
export function clausesOf(receipt: Receipt): string[] {
  const found = new Set<string>()
  const add = (clause: string | null): void => void (clause === null || found.add(clause))
  add(receipt.explanation.clause)
  for (const fact of receipt.explanation.facts) for (const source of fact.sources) add(source.clause)
  for (const check of receipt.checks) {
    add(check.clause)
    for (const source of check.sources) add(source.clause)
  }
  return [...found].toSorted(clauseOrder)
}

/** The receipt says SIMULATED while any part of it is: a source, the payout rail or the lender. Always so in the demo. */
export function isSimulated(receipt: Receipt): boolean {
  const sources = [...receipt.explanation.facts.flatMap((fact) => fact.sources), ...receipt.checks.flatMap((check) => check.sources), ...receipt.counterfactuals.flatMap((item) => item.sources)]
  return receipt.payout !== null || receipt.edi !== null || sources.some((source) => source.origin === 'SIMULATED')
}

const PASSED: ReadonlySet<CheckStatus> = new Set(['PASS', 'NOT_APPLICABLE'])
const NEEDS_A_LOOK: ReadonlySet<CheckStatus> = new Set(['FAIL', 'UNSURE', 'WAIVED_BY_OFFICER'])

export type CheckSummary = { allPassed: boolean; passed: number; needsLook: boolean }

export function summarise(checks: readonly ReceiptCheck[]): CheckSummary {
  return {
    allPassed: checks.length > 0 && checks.every((check) => PASSED.has(check.status)),
    passed: checks.filter((check) => check.status === 'PASS').length,
    needsLook: checks.some((check) => NEEDS_A_LOOK.has(check.status)),
  }
}

/** The lender's answer in words, from the fixed lines (copy deck 3.3): a refusal and silence show no reason. */
export function lenderLine(edi: ReceiptEdi, lang: Lang): Line {
  switch (edi.status) {
    case 'GRANTED':
      return { kind: 'copy', key: 'receipt.lender.granted', params: { instalment: edi.instalment_label, date: formatDate(edi.instalment_date, lang) } }
    case 'REFUSED':
      return { kind: 'copy', key: 'TRACK_EDI_REFUSED' }
    case 'NO_RESPONSE':
      return { kind: 'copy', key: 'TRACK_EDI_NO_RESPONSE' }
    case 'REQUESTED':
      return { kind: 'copy', key: 'TRACK_EDI_REQUESTED' }
  }
}

/** The claim this receipt is about, set to this decision so the bar and the buttons lead to the decision on screen. */
export function claimOfReceipt(items: readonly ClaimItem[] | null, receipt: Receipt | null): ClaimItem | null {
  if (items === null || receipt === null) return null
  const found = items.find((item) => item.claim_id === receipt.decision.claim_id)
  return found ? { ...found, decision_id: receipt.decision.id } : null
}
