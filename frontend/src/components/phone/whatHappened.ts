/**
 * "What happened" for one merchant (SPEC §17.2 monsoon timeline, §13 INSTALMENT_PAUSED, §19.2
 * MerchantDetail): the steps the demo narrates, read from data the page already has. The latest
 * decision (17:00 "Decision APPROVED"), its payout (17:04 "₹1,380 credited") and the instalment
 * pause message (17:05 "Tomorrow's ₹600 instalment paused"). Steps appear only once they happen.
 */
import type { MerchantDetail, Message } from '../../api/types'
import { actorLabel } from '../../lib/actors'

export type HappenedStep = { key: 'decision' | 'payout' | 'pause'; at: string; title: string; detail: string | null; tone: 'blue' | 'green' | 'amber' | 'red' }

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

export function happenedSteps(merchant: Pick<MerchantDetail, 'decisions' | 'payouts'>, messages: readonly Message[]): HappenedStep[] {
  return [decisionStep(merchant), payoutStep(merchant), pauseStep(messages)].filter((s): s is HappenedStep => s !== null)
}
