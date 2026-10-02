/**
 * "What happened" for one merchant (SPEC §17.2 monsoon timeline, §13 INSTALMENT_PAUSED, §19.2
 * MerchantDetail): the steps the demo narrates, read from data the page already has. The latest
 * decision (17:00 "Decision APPROVED"), its payout (17:04 "₹1,380 credited") and the instalment
 * (17:05). With the lender deciding the holiday (X4) that is two steps, "Lender asked" and the
 * lender's answer, read from `holiday_requests`; before that, the instalment pause message
 * ("Tomorrow's ₹600 instalment paused"). Steps appear only once they happen.
 */
import type { HolidayRequest, MerchantDetail, Message } from '../../api/types'
import { HOLIDAY_REASONS } from '../../content/holiday'
import { actorLabel } from '../../lib/actors'
import { weekdayDayLabel } from '../../lib/time'

export type HappenedStep = { key: 'decision' | 'payout' | 'asked' | 'answered' | 'pause'; at: string; title: string; detail: string | null; tone: 'blue' | 'green' | 'amber' | 'red' }

/** What the steps read: the decision, the payout and, once the lender is asked, its requests (absent or empty: the BUILT pause). */
type Happened = Pick<MerchantDetail, 'decisions' | 'payouts'> & Partial<Pick<MerchantDetail, 'holiday_requests'>>

/**
 * The English INSTALMENT_PAUSED line (SPEC §13.4): "Tomorrow's {instalment} instalment is paused.";
 * the illness replays run on the paused day itself, so the backend says "Today's" there.
 */
const PAUSE_TEMPLATE = /^(Tomorrow|Today)'s (.+) instalment is paused\.?$/

const OUTCOME_TONES: Readonly<Record<string, HappenedStep['tone']>> = Object.freeze({ APPROVED: 'blue', REFERRED: 'amber', DECLINED: 'red' })

function decisionStep(merchant: Pick<MerchantDetail, 'decisions'>): HappenedStep | null {
  const decision = merchant.decisions.at(-1)
  if (!decision) return null
  const by = actorLabel(decision.decided_by)
  return { key: 'decision', at: decision.decided_at, title: `Decision ${decision.outcome}`, detail: `${decision.amount_label} · ${by}`, tone: OUTCOME_TONES[decision.outcome] ?? 'blue' }
}

function payoutStep(merchant: Pick<MerchantDetail, 'payouts'>): HappenedStep | null {
  const payout = merchant.payouts.at(-1)
  if (!payout) return null
  if (payout.status === 'CREDITED' && payout.credited_at) return { key: 'payout', at: payout.credited_at, title: `${payout.amount_label} credited`, detail: 'with today’s settlement', tone: 'green' }
  return { key: 'payout', at: payout.created_at, title: `${payout.amount_label} on its way`, detail: payout.status === 'FAILED' ? 'payout failed' : 'with the next settlement', tone: payout.status === 'FAILED' ? 'red' : 'amber' }
}

function pauseStep(messages: readonly Message[]): HappenedStep | null {
  const message = messages.findLast((m) => m.direction === 'OUTBOUND' && PAUSE_TEMPLATE.test(m.text_en ?? ''))
  const match = message?.text_en ? PAUSE_TEMPLATE.exec(message.text_en) : null
  if (!message || !match) return null
  return { key: 'pause', at: message.created_at, title: `${match[1]}’s ${match[2]} instalment paused`, detail: 'lender notified', tone: 'blue' }
}

function askedStep(request: HolidayRequest): HappenedStep {
  const due = weekdayDayLabel(request.instalment_date)
  return { key: 'asked', at: request.requested_at, title: 'Lender asked', detail: `to pause the ${request.instalment_label} instalment due ${due}`, tone: 'blue' }
}

/** The lender's answer in its own terms; no answer is said as no answer, never as a pause. Null until it has answered. */
function answeredStep(request: HolidayRequest): HappenedStep | null {
  const at = request.decided_at
  if (request.status === 'REQUESTED' || at === null) return null
  if (request.status === 'GRANTED') return { key: 'answered', at, title: 'Lender answered', detail: 'paused · moved to the end of the loan, no penalty', tone: 'blue' }
  if (request.status === 'NO_RESPONSE') return { key: 'answered', at, title: 'Lender did not answer', detail: 'the instalment stays due · the payout is not affected', tone: 'amber' }
  const reason = request.reason_code === null ? null : HOLIDAY_REASONS[request.reason_code].en
  return { key: 'answered', at, title: 'Lender answered', detail: reason === null ? 'could not pause' : `could not pause · ${reason}`, tone: 'amber' }
}

function instalmentSteps(merchant: Happened, messages: readonly Message[]): HappenedStep[] {
  const request = merchant.holiday_requests?.at(-1)
  const steps = request ? [askedStep(request), answeredStep(request)] : [pauseStep(messages)]
  return steps.filter((s): s is HappenedStep => s !== null)
}

export function happenedSteps(merchant: Happened, messages: readonly Message[]): HappenedStep[] {
  return [decisionStep(merchant), payoutStep(merchant), ...instalmentSteps(merchant, messages)].filter((s): s is HappenedStep => s !== null)
}
