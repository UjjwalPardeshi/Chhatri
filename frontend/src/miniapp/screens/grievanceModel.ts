/**
 * What one step of the ladder says and offers (fs-06 7.2, 7.3 and 8.3, copy deck 13.1), as a pure function of the step
 * and the replay clock, so the wording rules are testable without a screen. A clock is shown only where a source
 * exists (our own hours, the portal's stated days); every other step says "to be confirmed". The portal is never
 * called late. Escalation is never blocked, but the button of the first step appears once the claims officer has
 * answered or the answer time has passed (screens-and-flows 7.1), and each later step has its own button.
 */
import type { Grievance, LadderStep, Respondent, StepId } from '../api/rights'
import type { RightsCopyKey } from '../copy/rights'

const MS_HOUR = 3_600_000
const MS_MINUTE = 60_000
const MS_DAY = 86_400_000

/** A sentence: its key, plain values, and values that are themselves sentences (the time left). */
export type Line = { key: RightsCopyKey; params: Record<string, string | number>; nested?: Record<string, Line> }
export type StepState = { key: RightsCopyKey }

const STATE_KEY: Readonly<Record<LadderStep['state'], RightsCopyKey>> = {
  NOT_STARTED: 'grv.state.locked',
  ACTIVE: 'grv.state.here',
  DONE: 'grv.state.done',
}

/** The three phases of our own claims officer's clock: ticking, answered (the case is closed) or past its hours. */
export function ownPhase(step: LadderStep, now: string | null): 'running' | 'answered' | 'overdue' {
  const clock = step.clock
  if (clock.kind !== 'OWN_SLA') return 'running'
  if (clock.state === 'OVERDUE') return 'overdue'
  if (clock.state !== null && clock.state !== 'RUNNING') return 'answered'
  return now !== null && Date.parse(now) > Date.parse(clock.due_by) ? 'overdue' : 'running'
}

/** Day n of the portal's stated days since the merchant filed, and whether they have passed; null before a filing date exists. */
export function portalDay(step: LadderStep, now: string | null): { n: number; days: number; past: boolean } | null {
  const clock = step.clock
  if (clock.kind !== 'PORTAL_STATED' || clock.started_at === null || now === null) return null
  const elapsed = Math.max(0, Math.floor((Date.parse(now) - Date.parse(clock.started_at)) / MS_DAY))
  return { n: Math.min(elapsed + 1, clock.days), days: clock.days, past: elapsed >= clock.days }
}

/** "5 hours" or "40 minutes" until the due time (never negative; "1 hour" and "1 minute" in the singular). */
export function timeLeft(dueBy: string, now: string | null): Line {
  const left = now === null || dueBy === '' ? 0 : Math.max(0, Date.parse(dueBy) - Date.parse(now))
  if (left >= MS_HOUR) {
    const hours = Math.ceil(left / MS_HOUR)
    return { key: hours === 1 ? 'grv.time.hour' : 'grv.time.hours', params: { n: hours } }
  }
  const minutes = Math.max(1, Math.ceil(left / MS_MINUTE))
  return { key: minutes === 1 ? 'grv.time.minute' : 'grv.time.minutes', params: { n: minutes } }
}

const CONFIRM_KEY: Readonly<Record<StepId, RightsCopyKey>> = {
  PAYTM_DISPUTE: 'grv.clock.confirm.paytm',
  INSURER_GRO: 'grv.clock.confirm.insurer',
  BIMA_BHAROSA: 'grv.clock.confirm.insurer',
  OMBUDSMAN: 'grv.clock.confirm.insurer',
  LENDER_GRIEVANCE: 'grv.clock.confirm.lender',
  PAYTM_SUPPORT: 'grv.clock.confirm.paytm',
}

/** The one line about time under a step name: our hours, the portal's days, or "to be confirmed". Never an invented number. */
export function clockLine(step: LadderStep): Line {
  const { clock } = step
  if (clock.kind === 'OWN_SLA') return { key: 'grv.clock.own', params: { sla_hours: clock.hours } }
  if (clock.kind === 'PORTAL_STATED') return { key: 'grv.clock.portal', params: { days: clock.days } }
  return { key: CONFIRM_KEY[step.id], params: {} }
}

/** The sentence of an ACTIVE step (fs-06 8.3), or null for a step that is not the current one. */
export function activeLine(step: LadderStep, now: string | null, filedDate: string | null): Line | null {
  if (step.state !== 'ACTIVE') return null
  if (step.id === 'PAYTM_DISPUTE') {
    const phase = ownPhase(step, now)
    if (phase === 'answered') return { key: 'grv.state.PAYTM_DISPUTE.answered', params: {} }
    if (phase === 'overdue') return { key: 'grv.state.PAYTM_DISPUTE.overdue', params: { sla_hours: step.clock.kind === 'OWN_SLA' ? step.clock.hours : 0 } }
    if (now === null) return null
    return { key: 'grv.state.PAYTM_DISPUTE.running', params: {}, nested: { time_left: timeLeft(step.clock.kind === 'OWN_SLA' ? step.clock.due_by : '', now) } }
  }
  if (step.id === 'BIMA_BHAROSA') {
    const day = portalDay(step, now)
    if (day === null) return { key: 'grv.clock.portal', params: { days: step.clock.kind === 'PORTAL_STATED' ? step.clock.days : 14 } }
    if (day.past) return { key: 'grv.state.BIMA_BHAROSA.past', params: { days: day.days } }
    return { key: 'grv.state.BIMA_BHAROSA.active', params: { date: filedDate ?? '', days: day.days, n: day.n } }
  }
  const key = `grv.state.${step.id}.active` as RightsCopyKey
  return { key, params: {} }
}

export function stateKey(step: LadderStep): RightsCopyKey {
  return STATE_KEY[step.state]
}

/** The next step's button, from the contract's `next_action` id, with the copy-deck key of its words. */
const ESCALATE_KEY: Readonly<Record<string, { key: RightsCopyKey; filing: boolean }>> = {
  ESCALATE_TO_INSURER_GRO: { key: 'grv.btn.to_gro', filing: false },
  ESCALATE_TO_BIMA_BHAROSA: { key: 'grv.btn.to_bharosa', filing: true },
  ESCALATE_TO_OMBUDSMAN: { key: 'grv.btn.to_ombudsman', filing: true },
}

export type Escalation = { key: RightsCopyKey; filing: boolean; from: StepId }

/** The escalate button of the current step: absent when resolved, on the last step, or (first step) before the answer or the late hour. */
export function escalation(grievance: Grievance, now: string | null): Escalation | null {
  if (grievance.status !== 'OPEN' || grievance.next_action === null) return null
  const target = ESCALATE_KEY[grievance.next_action.id]
  const current = grievance.ladder_steps.find((step) => step.id === grievance.current_step)
  if (!target || !current) return null
  if (current.id === 'PAYTM_DISPUTE' && ownPhase(current, now) === 'running') return null
  return { ...target, from: grievance.current_step }
}

export function isOutside(step: LadderStep): boolean {
  return step.delivery !== 'IN_CHHATRI'
}

export const respondentKey = (respondent: Respondent): RightsCopyKey => `grv.who.${respondent}`
