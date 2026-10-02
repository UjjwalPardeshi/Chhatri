/**
 * Mock cases and officer decisions (SPEC §9.4, §12). Case ids start at C-2291; `due_by` = opened +
 * dispute SLA (24 h). An officer approval of a referred personal claim re-runs the HARD checks and
 * records SOFT checks as WAIVED_BY_OFFICER in a new Decision that supersedes the referral.
 */
import type { Case, CaseEvidence, Check, Decision, SlipEvidence } from '../api/types'
import { MSG } from './catalogue'
import { roundToRupee } from './claims'
import { MOCK_OFFICER_ID, type MockMerchant } from './fixtures'
import { OFFICER_BADGE, payPersonal } from './personal'
import type { MockRuntime } from './runtime'
import { hourlyIndex, isoAt, isoPlusMinutes } from './scenarios'

const SLA_MINUTES = 24 * 60
const HOUR = 60
/** Tea-stall hourly profile, 06:00–21:00, in % of the day (SPEC §5.3: peaks 07–10 and 16–19). */
const TEA_PROFILE: readonly number[] = [5, 8, 9, 8, 6, 5, 5, 5, 5, 6, 8, 9, 8, 6, 4, 3]
const PROFILE_START_HOUR = 6

export class CaseError extends Error {
  readonly code: string
  readonly status: number
  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

function expectedVsActual(rt: MockRuntime, merchant: MockMerchant, day: string, silent: boolean, untilHour: number) {
  return TEA_PROFILE.slice(0, Math.max(0, untilHour - PROFILE_START_HOUR)).map((share, i) => {
    const hour = PROFILE_START_HOUR + i
    const expected = roundToRupee((merchant.expected_day_paise * share) / 100)
    const actual = silent ? 0 : roundToRupee((expected * hourlyIndex(rt.scenario, merchant.zone_id, hour)) / 100)
    return { hour: isoAt(day, hour * HOUR), expected_paise: expected, actual_paise: actual }
  })
}

function openCase(rt: MockRuntime, merchant: MockMerchant, kind: Case['kind'], summary: string, decision: Decision | null, evidence: CaseEvidence): Case {
  const opened: Case = {
    id: rt.nextCaseId(),
    kind,
    merchant_id: merchant.id,
    merchant_name: merchant.shop_name,
    status: 'OPEN',
    opened_at: rt.nowIso,
    due_by: isoPlusMinutes(rt.scenario.day, rt.minute, SLA_MINUTES),
    summary_en: summary,
    decision,
    evidence,
    resolution: null,
    resolved_by: null,
    resolved_at: null,
  }
  rt.cases = [...rt.cases, opened]
  rt.emit('case', { case: opened })
  rt.record('system', 'case.opened', 'case', opened.id, { kind, merchant_id: merchant.id })
  return opened
}

export function openDisputeCase(rt: MockRuntime, merchant: MockMerchant, text: string, decision: Decision | null): Case {
  const amount = decision ? `the ${decision.amount_label} area payout` : 'the area payout'
  const evidence: CaseEvidence = {
    expected_vs_actual: expectedVsActual(rt, merchant, rt.scenario.day, false, Math.floor(rt.minute / HOUR)),
    merchant_text: text,
    precedents: [],
  }
  const opened = openCase(rt, merchant, 'DISPUTE', `${merchant.shop_name} disputes ${amount}: "${text}"`, decision, evidence)
  rt.addFeed('case', `Case ${opened.id} opened: ${merchant.shop_name} disputes the amount`, { merchant_id: merchant.id })
  return opened
}

type ReviewEvidence = { slip: SlipEvidence; nameScore: number | null; silentDay: string }

export function openReviewCase(rt: MockRuntime, merchant: MockMerchant, decision: Decision, input: ReviewEvidence): Case {
  const evidence: CaseEvidence = {
    expected_vs_actual: expectedVsActual(rt, merchant, input.silentDay, true, 22),
    slip: input.slip,
    kyc_name: merchant.kyc_name,
    ...(input.nameScore === null ? {} : { name_score: input.nameScore }),
    silent_days: [input.silentDay],
    precedents: [],
  }
  const summary = `Personal claim ${decision.amount_label} for ${merchant.shop_name} referred: ${decision.referral_reason ?? 'needs review'}`
  return openCase(rt, merchant, 'PERSONAL_CLAIM_REVIEW', summary, decision, evidence)
}

/** SPEC §9.4: an officer approval records every SOFT check as WAIVED_BY_OFFICER (as the backend does). */
function waived(checks: readonly Check[]): Check[] {
  return checks.map((c) => (c.severity === 'SOFT' ? { ...c, status: 'WAIVED_BY_OFFICER', detail_en: `Waived by officer ${MOCK_OFFICER_ID} (was ${c.status}): ${c.detail_en}` } : c))
}

function officerDecision(rt: MockRuntime, previous: Decision, approve: boolean): Decision {
  const decision: Decision = {
    ...previous,
    id: rt.nextId('D'),
    outcome: approve ? 'APPROVED' : 'DECLINED',
    amount_paise: approve ? previous.amount_paise : 0,
    amount_label: approve ? previous.amount_label : '₹0',
    checks: approve ? waived(previous.checks) : previous.checks,
    decided_at: rt.nowIso,
    decided_by: `officer:${MOCK_OFFICER_ID}`,
    referral_reason: null,
    supersedes: previous.id,
  }
  rt.decisions.push(decision)
  rt.emit('decision', { decision })
  rt.record(decision.decided_by, 'decision.made', 'decision', decision.id, { outcome: decision.outcome, supersedes: previous.id })
  return decision
}

/** The backend's wording for a resolved dispute (replay/officer.py); disputes close, they never pay again. */
const DISPUTE_CONFIRMED = 'Payout confirmed by a claims officer'
const DISPUTE_REJECTED = 'Dispute declined by a claims officer'

export const DECLINE_REASON = {
  hi: 'पर्ची पर नाम आपके KYC से मेल नहीं खाता, इसलिए यह दावा मंज़ूर नहीं हो सका।',
  en: "The name on the slip doesn't match your KYC, so this claim can't be approved.",
}

export type OfficerOutcome = { decision: Decision | null; case: Case }

export function officerDecide(rt: MockRuntime, merchant: MockMerchant, caseId: string, approve: boolean, note: string): OfficerOutcome {
  const current = rt.cases.find((c) => c.id === caseId)
  if (!current) throw new CaseError('not_found', `case ${caseId} not found`, 404)
  if (current.status !== 'OPEN') throw new CaseError('conflict', `case ${caseId} is already ${current.status}`, 409)
  const officer = `officer:${MOCK_OFFICER_ID}`
  let decision = current.decision
  if (current.kind === 'PERSONAL_CLAIM_REVIEW' && current.decision?.outcome === 'REFERRED') {
    decision = officerDecision(rt, current.decision, approve)
    if (approve) payPersonal(rt, merchant, decision, MSG.officerApproved(merchant.owner_name_hi, merchant.owner_first_en, decision.amount_label), OFFICER_BADGE)
    else rt.send(merchant.id, { kind: 'TEXT', text: MSG.officerDeclined(merchant.owner_name_hi, merchant.owner_first_en, DECLINE_REASON.hi, DECLINE_REASON.en) })
  }
  const dispute = current.kind === 'DISPUTE'
  const status = dispute ? 'CLOSED' : approve ? 'APPROVED' : 'DECLINED'
  const defaultNote = dispute ? (approve ? DISPUTE_CONFIRMED : DISPUTE_REJECTED) : `${approve ? 'Approved' : 'Declined'} by ${officer}`
  const updated: Case = { ...current, status, decision, resolution: note.trim() || defaultNote, resolved_by: officer, resolved_at: rt.nowIso }
  rt.replaceCase(updated)
  rt.record(officer, approve ? 'case.approved' : 'case.declined', 'case', caseId, { note: updated.resolution })
  rt.addFeed('case', `Case ${caseId} ${approve ? 'approved' : 'declined'} by a claims officer`, { merchant_id: merchant.id })
  return { decision, case: updated }
}
