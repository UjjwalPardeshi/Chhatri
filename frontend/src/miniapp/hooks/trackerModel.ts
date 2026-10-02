/**
 * The claim tracker as a pure model (fs-04 section 9, H1). It turns one claim item, as the API recorded it, into what
 * the screens draw: the pill, the five steps with their state, words and times, the case chip and its clock, and
 * whether "This is wrong" is offered. The app displays states and never moves a claim: every fact below is read from
 * the item, the lines are fixed copy keys or the API's own sentences, and a line that needs a rule number the app
 * does not have is left out rather than guessed. An AREA claim that is REFERRED is a contract violation here too.
 */
import type { CaseStatus, ClaimItem, ClaimKind, ClaimStep, StepName, StepStatus } from '../../api/types'
import { ContractViolation } from '../api/parse'
import type { CopyKey, CopyParams } from '../lib/copy'

export type StepId = 'detected' | 'checked' | 'decided' | 'paid' | 'edi'
export type StepIcon = 'done' | 'working' | 'person' | 'waiting' | 'skipped' | 'stopped'
export type Tone = 'paid' | 'decided' | 'referred' | 'blocked' | 'neutral'
export type PillIcon = 'check' | 'clock' | 'person' | 'x' | 'hourglass' | 'scale'
/** The engine word the pill carries in `data-status`, plus the two states that are not a decision. */
export type PillWord = 'APPROVED' | 'REFERRED' | 'DECLINED' | 'WAITING_FOR_SLIP' | 'DISPUTE_OPEN' | 'DISPUTE_CLOSED'
export type Pill = { word: PillWord; labelKey: CopyKey; tone: Tone; icon: PillIcon }

/** A line of words: fixed copy with its facts, or the API's own sentence in both languages. */
export type Line = { kind: 'copy'; key: CopyKey; params?: CopyParams } | { kind: 'api'; hi: string | null; en: string | null }
export type Clock = { kind: 'left'; hours: number } | { kind: 'overdue' } | { kind: 'due'; at: string }

/** What the model needs besides the item: the two rule numbers it words, and the replay clock for the case clock. */
export type ModelContext = { slaHours: number | null; creditMinutes: number | null; now: string | null }

export type StepView = {
  id: StepId
  name: StepName
  titleKey: CopyKey
  /** The API's word for the step (`data-status`). */
  status: StepStatus
  result: ClaimStep['result']
  stateKey: CopyKey
  icon: StepIcon
  at: string | null
  headline: Line | null
  detail: Line | null
  /** Set on the officer's approval: the amount shown beside the line, never inside it (copy deck TRACK_DECIDED_OFFICER). */
  amountLabel: string | null
  /** The Paid step is the payout rail and the holiday step is the lender: both are simulated and say so. */
  simulated: 'payment' | 'lender' | null
}

export type ClaimView = {
  /** The id in `claim-card-{id}`: the claim, or the case for a dispute. */
  id: string
  kind: ClaimKind
  kindKey: CopyKey
  claimId: string | null
  disputedClaimId: string | null
  /** The claim whose detail screen draws this card: a dispute opens the claim it is about. */
  detailClaimId: string | null
  decisionId: string | null
  at: string
  amountLabel: string | null
  pill: Pill
  steps: StepView[]
  nextLine: Line | null
  caseChip: { caseId: string } | null
  clock: Clock | null
  caseId: string | null
  caseStatus: CaseStatus | null
  resolution: string | null
  paid: boolean
  officerApproved: boolean
  canDispute: boolean
}

const HOUR_MS = 3_600_000

const STEP_IDS: Readonly<Record<StepName, StepId>> = {
  Detected: 'detected',
  Checked: 'checked',
  Decided: 'decided',
  Paid: 'paid',
  'EDI holiday': 'edi',
}
const TITLE_KEYS: Readonly<Record<StepId, CopyKey>> = {
  detected: 'tracker.step.detected',
  checked: 'tracker.step.checked',
  decided: 'tracker.step.decided',
  paid: 'tracker.step.paid',
  edi: 'tracker.step.edi',
}
const KIND_KEYS: Readonly<Record<ClaimKind, CopyKey>> = { AREA: 'tracker.kind.area', PERSONAL: 'tracker.kind.personal', DISPUTE: 'tracker.kind.dispute' }

type State = { stateKey: CopyKey; icon: StepIcon }
const DONE: State = { stateKey: 'tracker.state.done', icon: 'done' }
const WORKING: State = { stateKey: 'tracker.state.now', icon: 'working' }
const WAITING: State = { stateKey: 'tracker.state.waiting', icon: 'waiting' }
const NOT_NEEDED: State = { stateKey: 'tracker.state.na', icon: 'skipped' }
const STOPPED: State = { stateKey: 'tracker.state.stopped', icon: 'stopped' }
const WITH_A_PERSON: State = { stateKey: 'claim.status.referred', icon: 'person' }

const copyLine = (key: CopyKey, params?: CopyParams): Line => (params ? { kind: 'copy', key, params } : { kind: 'copy', key })

function apiLine(step: ClaimStep): Line | null {
  return step.reason_hi === null && step.reason_en === null ? null : { kind: 'api', hi: step.reason_hi, en: step.reason_en }
}

function stateOf(step: ClaimStep): State {
  if (step.status === 'completed') return step.name === 'Decided' && step.result === 'DECLINED' ? STOPPED : DONE
  if (step.status === 'current') return step.name === 'Decided' && step.result === 'REFERRED' ? WITH_A_PERSON : WORKING
  return step.status === 'pending' ? WAITING : NOT_NEEDED
}

/** An officer approved a claim that the engine had sent to a person (fs-04 9.4): the case was resolved with APPROVED. */
export const isOfficerApproved = (item: ClaimItem): boolean =>
  item.kind === 'PERSONAL' && item.outcome === 'APPROVED' && item.case_id !== null && item.case_status === 'APPROVED'

export function isPaid(item: ClaimItem): boolean {
  return item.steps.find((step) => step.name === 'Paid')?.status === 'completed'
}

function decidedHeadline(item: ClaimItem, step: ClaimStep): Line | null {
  if (step.result === 'APPROVED') {
    if (isOfficerApproved(item)) return copyLine('TRACK_DECIDED_OFFICER')
    return item.amount_label === null ? null : copyLine('TRACK_DECIDED_AUTO', { amount: item.amount_label })
  }
  // A claim with a person says so once, in the state word of the step (`claim.status.referred`), not again as a headline.
  if (step.result === 'REFERRED') return null
  return step.result === 'DECLINED' ? copyLine('claim.status.declined') : null
}

function ediHeadline(step: ClaimStep): Line | null {
  if (step.status === 'current') return copyLine('TRACK_EDI_REQUESTED')
  if (step.result === 'REFUSED') return copyLine('TRACK_EDI_REFUSED')
  if (step.result === 'NO_RESPONSE') return copyLine('TRACK_EDI_NO_RESPONSE')
  return step.result === 'NO_LOAN' ? copyLine('TRACK_EDI_NONE') : null
}

function headlineOf(item: ClaimItem, step: ClaimStep): Line | null {
  switch (step.name) {
    case 'Detected':
      return step.status === 'current' && item.kind === 'PERSONAL' && item.outcome === null ? copyLine('claim.status.waiting_slip') : null
    case 'Decided':
      return decidedHeadline(item, step)
    case 'Paid':
      return step.status === 'current' && item.amount_label !== null ? copyLine('TRACK_PAID_PENDING', { amount: item.amount_label }) : null
    case 'EDI holiday':
      return ediHeadline(step)
    default:
      return null
  }
}

/** The lender's refusal and silence, and a missing loan, are said by the fixed line alone: no reason text, no code. */
const FIXED_LINE_ONLY = new Set<ClaimStep['result']>(['REFUSED', 'NO_RESPONSE', 'NO_LOAN'])

function detailOf(step: ClaimStep, ctx: ModelContext): Line | null {
  if (step.name === 'Paid' && step.status === 'current') return ctx.creditMinutes === null ? null : copyLine('TRACK_PAID_ETA', { minutes: ctx.creditMinutes })
  if (step.name === 'EDI holiday' && (step.status !== 'completed' || FIXED_LINE_ONLY.has(step.result))) return null
  if (step.name === 'Decided' && step.result === 'REFERRED') return null
  return apiLine(step)
}

function simulatedOf(step: ClaimStep): StepView['simulated'] {
  const happening = step.status === 'completed' || step.status === 'current'
  if (step.name === 'Paid') return happening ? 'payment' : null
  return step.name === 'EDI holiday' && happening && step.result !== 'NO_LOAN' ? 'lender' : null
}

function stepView(item: ClaimItem, step: ClaimStep, ctx: ModelContext): StepView {
  const id = STEP_IDS[step.name]
  return {
    id,
    name: step.name,
    titleKey: TITLE_KEYS[id],
    status: step.status,
    result: step.result,
    ...stateOf(step),
    at: step.at,
    headline: headlineOf(item, step),
    detail: detailOf(step, ctx),
    amountLabel: step.name === 'Decided' && isOfficerApproved(item) ? item.amount_label : null,
    simulated: simulatedOf(step),
  }
}

function pillOf(item: ClaimItem, paid: boolean): Pill {
  if (item.kind === 'DISPUTE') {
    return item.case_status === 'OPEN'
      ? { word: 'DISPUTE_OPEN', labelKey: 'claim.status.question_open', tone: 'referred', icon: 'scale' }
      : { word: 'DISPUTE_CLOSED', labelKey: 'claim.status.question_closed', tone: 'neutral', icon: 'check' }
  }
  if (item.outcome === null) return { word: 'WAITING_FOR_SLIP', labelKey: 'claim.status.waiting_slip', tone: 'neutral', icon: 'hourglass' }
  if (item.outcome === 'REFERRED') return { word: 'REFERRED', labelKey: 'claim.status.referred', tone: 'referred', icon: 'person' }
  if (item.outcome === 'DECLINED') return { word: 'DECLINED', labelKey: 'claim.status.declined', tone: 'blocked', icon: 'x' }
  const labelKey: CopyKey = isOfficerApproved(item) ? 'TRACK_DECIDED_OFFICER' : paid ? 'claim.status.paid' : 'claim.status.approved_pending'
  return { word: 'APPROVED', labelKey, tone: paid ? 'paid' : 'decided', icon: paid ? 'check' : 'clock' }
}

/** The clock of an open case: hours left rounded up, overdue once the time has passed, or the due time when the replay clock is unknown. */
function clockOf(item: ClaimItem, ctx: ModelContext): Clock | null {
  if (item.case_id === null || item.case_status !== 'OPEN' || item.due_by === null) return null
  const due = Date.parse(item.due_by)
  if (Number.isNaN(due)) return null
  const now = ctx.now === null ? Number.NaN : Date.parse(ctx.now)
  if (Number.isNaN(now)) return { kind: 'due', at: item.due_by }
  return due > now ? { kind: 'left', hours: Math.ceil((due - now) / HOUR_MS) } : { kind: 'overdue' }
}

function approvedNextLine(item: ClaimItem): Line {
  if (!isPaid(item)) return copyLine('tracker.next.after_decided')
  const holiday = item.steps.find((step) => step.name === 'EDI holiday')
  return holiday?.status === 'current' || holiday?.status === 'pending' ? copyLine('tracker.next.after_paid') : copyLine('tracker.next.done')
}

function nextLineOf(item: ClaimItem, ctx: ModelContext): Line | null {
  if (item.kind === 'DISPUTE') {
    if (item.case_status === 'OPEN') {
      return ctx.slaHours === null || item.case_id === null ? null : copyLine('TRACK_DISPUTE_OPEN', { case_id: item.case_id, sla_hours: ctx.slaHours })
    }
    return item.amount_label === null ? null : copyLine('TRACK_DISPUTE_CLOSED', { amount: item.amount_label })
  }
  if (item.outcome === 'REFERRED') return ctx.slaHours === null ? null : copyLine('tracker.next.referred', { sla_hours: ctx.slaHours })
  if (item.outcome === 'DECLINED') return copyLine('tracker.next.declined')
  return item.outcome === 'APPROVED' ? approvedNextLine(item) : null
}

/** The item that is a dispute about this claim: the newest one, because the API lists newest first. */
export function disputeFor(items: readonly ClaimItem[], claimId: string): ClaimItem | null {
  return items.find((item) => item.kind === 'DISPUTE' && item.disputed_claim_id === claimId) ?? null
}

export function findClaim(items: readonly ClaimItem[], claimId: string): ClaimItem | null {
  return items.find((item) => item.claim_id === claimId) ?? null
}

/** "This is wrong" is for a paid claim, and only while no dispute about it is open (fs-04 9.4, copy deck 3.1). */
export function canDispute(item: ClaimItem, all: readonly ClaimItem[]): boolean {
  if (item.kind === 'DISPUTE' || item.claim_id === null || item.outcome !== 'APPROVED' || !isPaid(item)) return false
  const openAboutIt = all.some((other) => other.kind === 'DISPUTE' && other.disputed_claim_id === item.claim_id && other.case_status === 'OPEN')
  return !openAboutIt
}

export function claimView(item: ClaimItem, all: readonly ClaimItem[], ctx: ModelContext): ClaimView {
  if (item.kind === 'AREA' && item.outcome === 'REFERRED') {
    throw new ContractViolation('an AREA claim can never be REFERRED (area claims carry HARD checks only)')
  }
  const paid = isPaid(item)
  const referred = item.outcome === 'REFERRED'
  return {
    id: item.claim_id ?? item.case_id ?? item.disputed_claim_id ?? '',
    kind: item.kind,
    kindKey: KIND_KEYS[item.kind],
    claimId: item.claim_id,
    disputedClaimId: item.disputed_claim_id,
    detailClaimId: item.claim_id ?? item.disputed_claim_id,
    decisionId: item.decision_id,
    at: item.claim_at,
    amountLabel: item.kind === 'DISPUTE' || item.outcome === 'APPROVED' ? item.amount_label : null,
    pill: pillOf(item, paid),
    steps: item.steps.map((step) => stepView(item, step, ctx)),
    nextLine: nextLineOf(item, ctx),
    caseChip: item.case_id !== null && (item.kind === 'DISPUTE' || referred) ? { caseId: item.case_id } : null,
    clock: clockOf(item, ctx),
    caseId: item.case_id,
    caseStatus: item.case_status,
    resolution: item.resolution,
    paid,
    officerApproved: isOfficerApproved(item),
    canDispute: canDispute(item, all),
  }
}

export function claimViews(items: readonly ClaimItem[], ctx: ModelContext): ClaimView[] {
  return items.map((item) => claimView(item, items, ctx))
}
