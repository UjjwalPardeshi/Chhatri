/**
 * Mock GET /api/merchants/{id}/claims (data-model 5.1, fs-04 section 9). One item per claim and one per dispute,
 * newest first. The five steps are built from the mock decisions, payouts, lender requests (x4_lender_request on),
 * instalment pauses and cases by the rules of fs-04 9.5, as the backend builds them: an AREA item is never REFERRED, a DECLINED claim skips Paid and the EDI
 * holiday, a merchant with no loan skips the EDI holiday, and a DISPUTE item has no steps and never changes the
 * amount. The step lines are the catalogue's (EXPLAIN_AREA_FORMULA, PAYOUT_CARD, INSTALMENT_PAUSED) and the
 * proposed Detected and Checked lines of the data-model example.
 */
import type { Case, ClaimItem, ClaimKind, ClaimStep, Decision, HolidayRequest, InstalmentPause, Payout, StepName, StepStatus } from '../../api/types'
import { HOLIDAY, HOLIDAY_REASONS, MSG, type Bilingual, type HolidayDay } from '../catalogue'
import { DECLINE_REASON } from '../cases'
import type { MockMerchant } from '../fixtures'
import { merchantParam, ok, type Route } from '../http'
import type { MockRuntime } from '../runtime'
import { addDays } from '../scenarios'
import { explanationOf } from './provenance'

type Line = Bilingual | null
type Facts = { rt: MockRuntime; merchant: MockMerchant; kind: ClaimKind; first: Decision; effective: Decision; payout: Payout | null }

const step = (name: StepName, status: StepStatus, result: ClaimStep['result'], at: string | null, line: Line): ClaimStep => ({
  name,
  status,
  result,
  at,
  reason_hi: line?.hi ?? null,
  reason_en: line?.en ?? null,
  reason_code: null,
})

/** The tracker lines of a lender request (backend TRACK_EDI_* keys, conversation/messages.py). */
const TRACK_EDI = {
  requested: { hi: 'हमने आपके लेंडर से कहा है। फ़ैसला लेंडर का होता है।', en: 'We asked your lender. The lender decides.' },
  refused: { hi: 'उपलब्ध नहीं। आपकी किस्त हमेशा की तरह देय है।', en: 'Not available. Your instalment is due as usual.' },
  noResponse: { hi: 'हम आपके लेंडर तक नहीं पहुँच सके। आपकी किस्त हमेशा की तरह देय है।', en: 'We could not reach your lender. Your instalment is due as usual.' },
} as const

/** The lender's request for this decision (x4_lender_request on), else the unconditional pause (flag off), as the backend reads them. */
function lenderAnswer(rt: MockRuntime, decision: Decision): { request: HolidayRequest | null; pause: InstalmentPause | null } {
  const request = rt.holidayRequests.findLast((r) => r.decision_id === decision.id) ?? null
  if (request) return { request, pause: null }
  return { request: null, pause: rt.pauses.findLast((p) => p.decision_id === decision.id) ?? null }
}

/** The day the instalment falls on, from the day the lender answered (the chat's tomorrow / today / date). */
function dueDay(instalmentDate: string, answeredAt: string): HolidayDay {
  const answered = answeredAt.slice(0, 10)
  if (instalmentDate === answered) return 'today'
  return instalmentDate === addDays(answered, 1) ? 'tomorrow' : { on: instalmentDate }
}

function requestStep(request: HolidayRequest): ClaimStep {
  if (request.status === 'REQUESTED') return step('EDI holiday', 'current', null, null, TRACK_EDI.requested)
  const answered = request.decided_at ?? request.requested_at
  if (request.status === 'GRANTED') {
    return step('EDI holiday', 'completed', 'GRANTED', answered, HOLIDAY.granted(request.instalment_label, dueDay(request.instalment_date, answered)))
  }
  if (request.status === 'NO_RESPONSE') return step('EDI holiday', 'completed', 'NO_RESPONSE', answered, TRACK_EDI.noResponse)
  const code = request.reason_code ?? 'FLAG_OFF'
  const why = HOLIDAY_REASONS[code]
  const line = { hi: `${TRACK_EDI.refused.hi} लेंडर ने मना किया: ${why.hi}।`, en: `${TRACK_EDI.refused.en} The lender said no: ${why.en}.` }
  return { ...step('EDI holiday', 'completed', 'REFUSED', answered, line), reason_code: code }
}

function detectedAt(f: Facts): string {
  if (f.kind === 'AREA') return f.rt.triggers.find((t) => t.zone_id === f.merchant.zone_id)?.fired_at ?? f.first.decided_at
  return f.rt.audit.find((e) => e.action === 'silence.detected' && e.subject_id === f.merchant.id)?.at ?? f.first.decided_at
}

const detectedLine = (dropPct: number | null): Line =>
  dropPct === null ? null : { hi: `अलर्ट के दौरान आपके इलाके की बिक्री ${dropPct}% गिरी।`, en: `Your area's sales fell ${dropPct}% during the alert.` }

function checkedLine(decision: Decision): Line {
  const n = decision.checks.length
  return decision.checks.every((c) => c.status === 'PASS') ? { hi: `सभी ${n} जाँचें पास हुईं।`, en: `All ${n} checks passed.` } : null
}

function decidedLine(decision: Decision): Line {
  if (decision.outcome === 'APPROVED') {
    const { formula_hi, formula_en } = explanationOf(decision)
    return { hi: `आपके भुगतान का हिसाब: ${formula_hi}`, en: `How your payout was worked out: ${formula_en}` }
  }
  return decision.outcome === 'DECLINED' ? DECLINE_REASON : null
}

function paidStep(f: Facts): ClaimStep {
  if (f.effective.outcome === 'DECLINED') return step('Paid', 'skipped', null, null, null)
  if (f.effective.outcome === 'REFERRED') return step('Paid', 'pending', null, null, null)
  if (f.payout?.status === 'CREDITED') return step('Paid', 'completed', null, f.payout.credited_at, { hi: MSG.payoutCard.hi, en: MSG.payoutCard.en })
  return step('Paid', 'current', null, null, null)
}

function ediStep(f: Facts, paid: ClaimStep): ClaimStep {
  if (f.effective.outcome === 'DECLINED') return step('EDI holiday', 'skipped', null, null, null)
  if (f.effective.outcome === 'REFERRED') return step('EDI holiday', 'pending', null, null, null)
  if (f.merchant.instalment_paise === null) return step('EDI holiday', 'skipped', 'NO_LOAN', null, null)
  const { request, pause } = lenderAnswer(f.rt, f.effective)
  if (request) return requestStep(request)
  if (pause) return step('EDI holiday', 'completed', 'GRANTED', pause.created_at, MSG.instalmentPaused(pause.amount_label))
  return step('EDI holiday', paid.status === 'completed' ? 'current' : 'pending', null, null, null)
}

function decidedStep(f: Facts): ClaimStep {
  const { effective } = f
  const status: StepStatus = effective.outcome === 'REFERRED' ? 'current' : 'completed'
  return step('Decided', status, effective.outcome, status === 'current' ? null : effective.decided_at, decidedLine(effective))
}

function stepsOf(f: Facts): ClaimStep[] {
  const paid = paidStep(f)
  return [
    step('Detected', 'completed', null, detectedAt(f), detectedLine(f.kind === 'AREA' ? explanationOf(f.first).drop_pct : null)),
    step('Checked', 'completed', null, f.first.decided_at, checkedLine(f.first)),
    decidedStep(f),
    paid,
    ediStep(f, paid),
  ]
}

function claimItem(rt: MockRuntime, merchant: MockMerchant, first: Decision, effective: Decision): ClaimItem {
  const kind: ClaimKind = explanationOf(first).drop_pct === null ? 'PERSONAL' : 'AREA'
  const trigger = kind === 'AREA' ? (rt.triggers.find((t) => t.zone_id === merchant.zone_id) ?? null) : null
  const kase = rt.cases.find((c) => c.kind === 'PERSONAL_CLAIM_REVIEW' && c.decision?.claim_id === first.claim_id) ?? null
  const payout = rt.payouts.find((p) => p.decision_id === effective.id) ?? null
  return {
    claim_id: first.claim_id,
    disputed_claim_id: null,
    kind,
    claim_at: trigger?.fired_at ?? first.decided_at,
    zone_id: kind === 'AREA' ? merchant.zone_id : null,
    trigger_id: trigger?.id ?? null,
    decision_id: effective.id,
    outcome: effective.outcome,
    amount_paise: effective.amount_paise,
    amount_label: effective.amount_label,
    steps: stepsOf({ rt, merchant, kind, first, effective, payout }),
    case_id: kase?.id ?? null,
    case_status: kase?.status ?? null,
    due_by: kase?.due_by ?? null,
    resolution: kase?.resolution ?? null,
  }
}

/** A dispute is a separate card about the latest paid decision. One about nothing paid is left out: there is no claim to point at. */
function disputeItem(merchant: MockMerchant, kase: Case & { decision: Decision }): ClaimItem {
  const { decision } = kase
  return {
    claim_id: null,
    disputed_claim_id: decision.claim_id,
    kind: 'DISPUTE',
    claim_at: kase.opened_at,
    zone_id: merchant.zone_id,
    trigger_id: null,
    decision_id: decision.id,
    outcome: decision.outcome,
    amount_paise: decision.amount_paise,
    amount_label: decision.amount_label,
    steps: [],
    case_id: kase.id,
    case_status: kase.status,
    due_by: kase.due_by,
    resolution: kase.resolution,
  }
}

const hasDecision = (c: Case): c is Case & { decision: Decision } => c.decision !== null

/** Newest first; items made at the same minute keep the later one on top. */
export function claimItems(rt: MockRuntime, merchant: MockMerchant): ClaimItem[] {
  const mine = rt.decisions.filter((d) => d.merchant_id === merchant.id)
  const claimIds = [...new Set(mine.map((d) => d.claim_id))]
  const claims = claimIds.map((id) => {
    const decisions = mine.filter((d) => d.claim_id === id)
    return claimItem(rt, merchant, decisions[0], decisions[decisions.length - 1])
  })
  const disputes = rt.cases.filter((c) => c.merchant_id === merchant.id && c.kind === 'DISPUTE').filter(hasDecision).map((c) => disputeItem(merchant, c))
  return [...claims, ...disputes]
    .map((item, index) => ({ item, index }))
    .toSorted((a, b) => b.item.claim_at.localeCompare(a.item.claim_at) || b.index - a.index)
    .map(({ item }) => item)
}

export const TRACKER_ROUTES: readonly Route[] = [
  {
    method: 'GET',
    pattern: /^\/api\/merchants\/(S-\d{4})\/claims$/,
    handler: (c) => {
      const items = claimItems(c.backend.runtime, merchantParam(c))
      return ok(items, { total: items.length, limit: items.length, offset: 0 })
    },
  },
]
