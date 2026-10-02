/**
 * Mock GET and POST /api/merchants/{id}/grievances (N5, data-model 5.4, fs-06 sections 7 and 8; flag n5_grievances, 404
 * `not_found` while it is off). The respondent router is the fixed table of fs-06 7.1; the ladders and the clocks are
 * the ones of 7.2 (only our own 24 hours and the 14 days the portal states carry a time, every other step is "to be
 * confirmed"). A grievance of a payout or a declined claim opens the same DISPUTE case as the chat path and sends
 * DISPUTE_ACK and the case chip. The static demo states plainly that nothing is sent to an insurer: every step outside
 * Chhatri is SIMULATED or SELF_REPORTED. Records live per scenario load (per `MockRuntime`), like the cases.
 */
import type { Case, Decision } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import { MAX_COMPLAINT_CHARS, GRIEVANCE_TOPICS, STEP_IDS, TOPIC_RESPONDENT, type Grievance, type GrievanceTopic, type LadderClock, type LadderStep, type Respondent, type StepId } from '../../miniapp/api/rights'
import { MockHttpError } from '../backend'
import { openOrFindDispute } from '../cases'
import { MSG } from '../catalogue'
import { POLICY_RULES } from '../fixtures'
import { bodyField, invalid, merchantParam, notFound, ok, type Route, type RouteContext } from '../http'
import type { MockRuntime } from '../runtime'

const FLAG = 'n5_grievances'
const PORTAL_DAYS = 14
const LADDERS: Readonly<Record<Respondent, readonly StepId[]>> = {
  INSURER: ['PAYTM_DISPUTE', 'INSURER_GRO', 'BIMA_BHAROSA', 'OMBUDSMAN'],
  LENDER: ['LENDER_GRIEVANCE'],
  PAYTM: ['PAYTM_SUPPORT'],
}
const ROUTER = TOPIC_RESPONDENT
const NAMES: Readonly<Record<StepId, { name: string; delivery: LadderStep['delivery'] }>> = {
  PAYTM_DISPUTE: { name: 'Our claims officer', delivery: 'IN_CHHATRI' },
  INSURER_GRO: { name: "The insurer's grievance officer", delivery: 'SIMULATED' },
  BIMA_BHAROSA: { name: 'IRDAI Bima Bharosa portal', delivery: 'SELF_REPORTED' },
  OMBUDSMAN: { name: 'Insurance Ombudsman', delivery: 'SELF_REPORTED' },
  LENDER_GRIEVANCE: { name: "The lender's grievance officer", delivery: 'SIMULATED' },
  PAYTM_SUPPORT: { name: 'Paytm support', delivery: 'SIMULATED' },
}
const CONFIRM_NOTE: Readonly<Partial<Record<StepId, string>>> = {
  INSURER_GRO: 'Response time to be confirmed with the insurer',
  OMBUDSMAN: 'No response time is stated. The service is free to the policyholder',
  LENDER_GRIEVANCE: 'Response time to be confirmed with the lender',
  PAYTM_SUPPORT: 'Response time to be confirmed',
}
const NEXT_ACTION: Readonly<Partial<Record<StepId, { id: string; label_en: string }>>> = {
  PAYTM_DISPUTE: { id: 'ESCALATE_TO_INSURER_GRO', label_en: "Send this to the insurer's grievance officer" },
  INSURER_GRO: { id: 'ESCALATE_TO_BIMA_BHAROSA', label_en: 'Complain on the Bima Bharosa portal' },
  BIMA_BHAROSA: { id: 'ESCALATE_TO_OMBUDSMAN', label_en: 'Approach the Insurance Ombudsman' },
}

type Record_ = {
  id: string
  merchantId: string
  topic: GrievanceTopic
  respondent: Respondent
  decisionId: string | null
  caseId: string | null
  status: 'OPEN' | 'RESOLVED'
  openedAt: string
  current: StepId
  entered: Partial<Record<StepId, string>>
}

const MEMORY = new WeakMap<MockRuntime, Record_[]>()
const records = (rt: MockRuntime): Record_[] => {
  const known = MEMORY.get(rt)
  if (known) return known
  const fresh: Record_[] = []
  MEMORY.set(rt, fresh)
  return fresh
}

function requireFlag(): void {
  if (!isFeatureEnabled(FLAG)) throw notFound('route')
}

function clockOf(rt: MockRuntime, record: Record_, step: StepId): LadderClock {
  if (step === 'PAYTM_DISPUTE') {
    const linked = rt.cases.find((c) => c.id === record.caseId)
    const due = linked?.due_by ?? record.openedAt
    const answered = linked !== undefined && linked.status !== 'OPEN'
    const late = Date.parse(rt.nowIso) > Date.parse(due)
    return { kind: 'OWN_SLA', hours: POLICY_RULES.dispute_sla_hours, due_by: due, state: answered ? 'STOPPED' : late ? 'OVERDUE' : 'RUNNING' }
  }
  if (step === 'BIMA_BHAROSA') {
    return { kind: 'PORTAL_STATED', days: PORTAL_DAYS, started_at: record.entered[step] ?? null, statement_en: `The portal says complaints are attended within ${PORTAL_DAYS} days`, state: null }
  }
  return { kind: 'TO_CONFIRM', note_en: CONFIRM_NOTE[step] ?? 'Response time to be confirmed' }
}

function view(rt: MockRuntime, record: Record_): Grievance {
  const ladder = LADDERS[record.respondent]
  const at = ladder.indexOf(record.current)
  const steps = ladder.map((id, index): LadderStep => {
    const state = index < at ? 'DONE' : index === at ? (record.status === 'RESOLVED' ? 'DONE' : 'ACTIVE') : 'NOT_STARTED'
    const entered = record.entered[id]
    return { level: index + 1, id, ...NAMES[id], state, ...(entered ? { entered_at: entered } : {}), clock: clockOf(rt, record, id) } as LadderStep
  })
  return {
    grievance_id: record.id,
    kind: record.topic === 'PAYOUT_AMOUNT' || record.topic === 'CLAIM_DECLINED' ? 'DISPUTE' : 'COMPLAINT',
    topic: record.topic,
    respondent: record.respondent,
    decision_id: record.decisionId,
    case_id: record.caseId,
    status: record.status,
    opened_at: record.openedAt,
    current_step: record.current,
    ladder_steps: steps,
    next_action: record.status === 'OPEN' ? (NEXT_ACTION[record.current] ?? null) : null,
  }
}

const decisionsOf = (rt: MockRuntime, merchantId: string): Decision[] => rt.decisions.filter((d) => d.merchant_id === merchantId)

function latestPaid(rt: MockRuntime, merchantId: string): Decision | null {
  const credited = new Set(rt.payouts.filter((p) => p.merchant_id === merchantId && p.status === 'CREDITED').map((p) => p.decision_id))
  return decisionsOf(rt, merchantId).toReversed().find((d) => credited.has(d.id)) ?? null
}

const latestDeclined = (rt: MockRuntime, merchantId: string): Decision | null => decisionsOf(rt, merchantId).toReversed().find((d) => d.outcome === 'DECLINED') ?? null

function openReviewCase(rt: MockRuntime, merchantId: string): Case | null {
  return rt.cases.find((c) => c.merchant_id === merchantId && c.kind === 'PERSONAL_CLAIM_REVIEW' && c.status === 'OPEN') ?? null
}

function openGrievance(ctx: RouteContext): { grievance: Grievance; created: boolean } {
  const rt = ctx.backend.runtime
  const merchant = merchantParam(ctx)
  const topic = bodyField(ctx.body, 'topic')
  const text = bodyField(ctx.body, 'text')
  const wanted = bodyField(ctx.body, 'decision_id')
  if (typeof topic !== 'string' || !(GRIEVANCE_TOPICS as readonly string[]).includes(topic)) throw invalid('topic', 'one of the topics of the list')
  if (typeof text !== 'string' || text.trim().length === 0 || text.length > MAX_COMPLAINT_CHARS) throw invalid('text', `1 to ${MAX_COMPLAINT_CHARS} characters`)
  if (wanted !== undefined && typeof wanted !== 'string') throw invalid('decision_id', 'must be a decision id')
  const kind = topic as GrievanceTopic
  const decision = kind === 'PAYOUT_AMOUNT' ? latestPaid(rt, merchant.id) : kind === 'CLAIM_DECLINED' ? latestDeclined(rt, merchant.id) : (decisionsOf(rt, merchant.id).find((d) => d.id === wanted) ?? null)
  const needsDecision = kind === 'PAYOUT_AMOUNT' || kind === 'CLAIM_DECLINED'
  if (needsDecision && !decision) throw invalid('decision_id', 'there is no decision to dispute yet')
  const review = kind === 'CLAIM_SLOW' ? openReviewCase(rt, merchant.id) : null
  if (kind === 'CLAIM_SLOW' && !review) throw invalid('topic', 'no claim is waiting for review')
  const decisionId = needsDecision ? (decision?.id ?? null) : null
  const existing = records(rt).find((r) => r.merchantId === merchant.id && r.status === 'OPEN' && r.topic === kind && r.decisionId === decisionId)
  if (existing) return { grievance: view(rt, existing), created: false }
  const respondent = ROUTER[kind]
  let caseId: string | null = review?.id ?? null
  if (needsDecision) {
    const { opened, already } = openOrFindDispute(rt, merchant, text.trim(), decision)
    caseId = opened.id
    rt.send(merchant.id, { kind: 'TEXT', text: already ? MSG.disputeAlreadyOpen(caseId) : MSG.disputeAck })
    rt.send(merchant.id, { kind: 'CASE_CHIP', text: MSG.caseChip(caseId), meta: { case_id: caseId } })
  }
  const first = LADDERS[respondent][0]
  const record: Record_ = { id: rt.nextId('GR'), merchantId: merchant.id, topic: kind, respondent, decisionId, caseId, status: 'OPEN', openedAt: rt.nowIso, current: first, entered: { [first]: rt.nowIso } }
  records(rt).push(record)
  rt.record(`merchant:${merchant.id}`, 'grievance.open', 'grievance', record.id, { merchant_id: merchant.id, topic: kind, respondent, decision_id: decisionId, case_id: caseId, first_step: first })
  return { grievance: view(rt, record), created: true }
}

function target(ctx: RouteContext): Record_ {
  const rt = ctx.backend.runtime
  const id = bodyField(ctx.body, 'grievance_id')
  const found = records(rt).find((r) => r.id === id && r.merchantId === merchantParam(ctx).id)
  if (!found) throw notFound(`grievance ${String(id)}`)
  return found
}

function escalate(ctx: RouteContext): Grievance {
  const rt = ctx.backend.runtime
  const record = target(ctx)
  const from = bodyField(ctx.body, 'escalate_from')
  const filedOn = bodyField(ctx.body, 'filed_on')
  if (typeof from !== 'string' || !(STEP_IDS as readonly string[]).includes(from)) throw invalid('escalate_from', 'must be a step id')
  if (filedOn !== undefined && (typeof filedOn !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(filedOn))) throw invalid('filed_on', 'use a date like 2025-08-25')
  const ladder = LADDERS[record.respondent]
  const next = ladder[ladder.indexOf(record.current) + 1]
  if (record.status !== 'OPEN' || from !== record.current || next === undefined) throw new MockHttpError('conflict', 'this grievance cannot move on from that step', 409)
  const enteredAt = typeof filedOn === 'string' ? `${filedOn}T00:00:00+05:30` : rt.nowIso
  record.current = next
  record.entered = { ...record.entered, [next]: enteredAt }
  rt.record(`merchant:${record.merchantId}`, 'grievance.escalate', 'grievance', record.id, { from, to: next, filed_on: typeof filedOn === 'string' ? filedOn : null, clock_kind: clockOf(rt, record, next).kind })
  return view(rt, record)
}

function resolve(ctx: RouteContext): Grievance {
  const rt = ctx.backend.runtime
  const record = target(ctx)
  if (record.status !== 'OPEN') throw new MockHttpError('conflict', 'this grievance is already solved', 409)
  record.status = 'RESOLVED'
  rt.record(`merchant:${record.merchantId}`, 'grievance.resolve', 'grievance', record.id, { step: record.current })
  return view(rt, record)
}

function post(ctx: RouteContext) {
  requireFlag()
  const action = bodyField(ctx.body, 'action')
  if (action === 'OPEN') {
    return ok(openGrievance(ctx).grievance)
  }
  if (action === 'ESCALATE') return ok(escalate(ctx))
  if (action === 'RESOLVE') return ok(resolve(ctx))
  throw invalid('action', 'OPEN, ESCALATE or RESOLVE')
}

export const GRIEVANCE_ROUTES: readonly Route[] = [
  {
    method: 'GET',
    pattern: /^\/api\/merchants\/(S-\d{4})\/grievances$/,
    handler: (ctx) => {
      requireFlag()
      const merchant = merchantParam(ctx)
      const rt = ctx.backend.runtime
      const mine = records(rt).filter((r) => r.merchantId === merchant.id).toReversed().map((r) => view(rt, r))
      return ok(mine, { total: mine.length, limit: mine.length, offset: 0 })
    },
  },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/grievances$/, handler: post },
]
