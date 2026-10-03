/**
 * What happens after a payout is credited (fs-04 S5): a short ordered list read from the decision's receipt and the
 * cover, and from nothing else. The money (its label, and when it was credited), the lender's answer on the
 * instalment (the fixed line for the lender's own answer, never "Chhatri paused": the lender decides), what to do if
 * the amount looks wrong (the dispute button, with the clock of the first step when the receipt names one), and that
 * the cover continues (only while the cover is active and paid ahead). A step whose data is missing is left out, and a
 * payout that is not credited has no list at all.
 */
import type { Cover, Receipt } from '../../api/types'
import type { Line } from '../hooks/trackerModel'
import { formatDate, formatDateTime } from '../lib/format'
import type { Lang } from '../lib/lang'
import { isCredited, lenderLine } from './ReceiptRows'

export type NextStepId = 'money' | 'lender' | 'wrong' | 'cover'

/** One step: its line, a line under it (the dispute clock), and the SIMULATED part it names (the payout rail, the lender). */
export type NextStep = { id: NextStepId; line: Line; note: Line | null; simulated: 'payment' | 'lender' | null }

/** `canDispute`: the claim screen offers "This is wrong" (a paid claim with no open question about it). */
export type NextStepsInput = { receipt: Receipt; cover: Cover | null; canDispute: boolean }

function moneyStep({ payout }: Receipt, lang: Lang): NextStep | null {
  if (payout?.status !== 'CREDITED' || payout.credited_at === null) return null
  const params = { amount: payout.amount_label, time: formatDateTime(payout.credited_at, lang) }
  return { id: 'money', line: { kind: 'copy', key: 'claim.next.money', params }, note: null, simulated: 'payment' }
}

/** The lender block is the lender's request for this decision: null while none was made, so there is no answer to show. */
function lenderStep({ edi }: Receipt, lang: Lang): NextStep | null {
  return edi === null ? null : { id: 'lender', line: lenderLine(edi, lang), note: null, simulated: 'lender' }
}

function wrongStep({ grievance }: Receipt, canDispute: boolean): NextStep | null {
  if (!canDispute || !grievance.dispute_allowed) return null
  const hours = grievance.first_step_hours
  const note: Line | null = hours > 0 ? { kind: 'copy', key: 'grv.clock.own', params: { sla_hours: hours } } : null
  return { id: 'wrong', line: { kind: 'copy', key: 'claim.next.wrong' }, note, simulated: null }
}

function coverStep(cover: Cover | null, lang: Lang): NextStep | null {
  if (cover?.status !== 'ACTIVE' || cover.premium_due || cover.prepaid_through === null) return null
  return { id: 'cover', line: { kind: 'copy', key: 'claim.next.cover', params: { date: formatDate(cover.prepaid_through, lang) } }, note: null, simulated: null }
}

export function nextSteps({ receipt, cover, canDispute }: NextStepsInput, lang: Lang): NextStep[] {
  if (!isCredited(receipt)) return []
  const steps = [moneyStep(receipt, lang), lenderStep(receipt, lang), wrongStep(receipt, canDispute), coverStep(cover, lang)]
  return steps.filter((step): step is NextStep => step !== null)
}
