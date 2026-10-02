/**
 * Claim and receipt fixtures for the mini-app tests (cards 3.10): the claim items of fs-04 section 9.5, one per
 * situation, in the shape the claims route sends. Each builder returns a new object, so a test may change a copy.
 */
import type { ClaimItem, ClaimStep, DecisionOutcome, Receipt, StepName, StepStatus } from '../api/types'

export const T = {
  detected: '2025-08-19T17:00:00+05:30',
  paid: '2025-08-19T17:04:00+05:30',
  edi: '2025-08-19T17:05:00+05:30',
  slip: '2025-08-21T11:20:00+05:30',
} as const

const NAMES: readonly StepName[] = ['Detected', 'Checked', 'Decided', 'Paid', 'EDI holiday']

type StepSpec = [status: StepStatus, result?: ClaimStep['result'], at?: string | null, line?: [hi: string, en: string] | null]

export function steps(...specs: StepSpec[]): ClaimStep[] {
  return NAMES.map((name, index) => {
    const [status, result = null, at = null, line = null] = specs[index] ?? ['pending']
    return { name, status, result, at, reason_hi: line?.[0] ?? null, reason_en: line?.[1] ?? null, reason_code: null }
  })
}

const FORMULA: [string, string] = ['आपके भुगतान का हिसाब: ₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380', 'How your payout was worked out: ½ × ₹4,380 × 63% = ₹1,380']
const DETECTED: [string, string] = ['अलर्ट के दौरान आपके इलाके की बिक्री 63% गिरी।', "Your area's sales fell 63% during the alert."]
const CHECKED: [string, string] = ['सभी 9 जाँचें पास हुईं।', 'All 9 checks passed.']
const CREDITED: [string, string] = ['आज के सेटलमेंट के साथ जमा', "Credited with today's settlement"]
const PAUSED: [string, string] = ['कल की ₹600 की किस्त रोक दी गई है।', "Tomorrow's ₹600 instalment is paused."]
const DECLINE: [string, string] = ['पर्ची का नाम आपके KYC से मेल नहीं खाता, इसलिए यह दावा मंज़ूर नहीं हो सकता।', "The name on the slip doesn't match your KYC, so this claim can't be approved."]

export function claim(over: Partial<ClaimItem> = {}): ClaimItem {
  return {
    claim_id: 'CL-000142',
    disputed_claim_id: null,
    kind: 'AREA',
    claim_at: T.detected,
    zone_id: 'Z7',
    trigger_id: 'E-Z7-20250819',
    decision_id: 'D-000142',
    outcome: 'APPROVED',
    amount_paise: 138_000,
    amount_label: '₹1,380',
    steps: steps(['completed', null, T.detected, DETECTED], ['completed', null, T.detected, CHECKED], ['completed', 'APPROVED', T.detected, FORMULA], ['completed', null, T.paid, CREDITED], ['completed', 'GRANTED', T.edi, PAUSED]),
    case_id: null,
    case_status: null,
    due_by: null,
    resolution: null,
    ...over,
  }
}

/** Area, approved, the credit is not in yet. */
export const areaCreditPending = (): ClaimItem =>
  claim({ steps: steps(['completed', null, T.detected, DETECTED], ['completed', null, T.detected, CHECKED], ['completed', 'APPROVED', T.detected, FORMULA], ['current'], ['pending']) })

/** Area, paid, the lender is asked and has not answered. */
export const areaLenderAsked = (): ClaimItem =>
  claim({ steps: steps(['completed', null, T.detected, DETECTED], ['completed', null, T.detected, CHECKED], ['completed', 'APPROVED', T.detected, FORMULA], ['completed', null, T.paid, CREDITED], ['current']) })

export const areaLenderGranted = (): ClaimItem => claim()

/** The lender refused: the reason code stays on the step (the console shows it), the app never does. */
export function areaLenderRefused(): ClaimItem {
  const base = areaLenderAsked()
  const refused: ClaimStep = { name: 'EDI holiday', status: 'completed', result: 'REFUSED', at: T.edi, reason_hi: 'आपका लेंडर किस्त नहीं रोक सका: लोन की कुछ रकम बकाया है।', reason_en: 'Your lender could not pause the instalment: the loan has an amount overdue.', reason_code: 'IN_ARREARS' }
  return { ...base, steps: [...base.steps.slice(0, 4), refused] }
}

export function areaNoLoan(): ClaimItem {
  const base = claim()
  const none: ClaimStep = { name: 'EDI holiday', status: 'skipped', result: 'NO_LOAN', at: null, reason_hi: null, reason_en: null, reason_code: null }
  return { ...base, steps: [...base.steps.slice(0, 4), none] }
}

export const areaDeclined = (): ClaimItem =>
  claim({ outcome: 'DECLINED', amount_paise: 0, amount_label: '₹0', steps: steps(['completed', null, T.detected, DETECTED], ['completed', null, T.detected, null], ['completed', 'DECLINED', T.detected, DECLINE], ['skipped'], ['skipped']) })

/** A hospital-cash claim whose slip has not come yet: no decision, no amount, Detected is the current step. */
export const personalWaitingForSlip = (): ClaimItem =>
  claim({ claim_id: 'CL-000001', kind: 'PERSONAL', trigger_id: null, zone_id: null, decision_id: null, outcome: null, amount_paise: null, amount_label: null, claim_at: T.slip, steps: steps(['current']) })

export const personalReferred = (): ClaimItem =>
  claim({
    claim_id: 'CL-000001',
    kind: 'PERSONAL',
    trigger_id: null,
    zone_id: null,
    decision_id: 'D-000001',
    outcome: 'REFERRED',
    amount_paise: 0,
    amount_label: '₹0',
    claim_at: T.slip,
    steps: steps(['completed', null, T.slip], ['completed', null, T.slip], ['current', 'REFERRED'], ['pending'], ['pending']),
    case_id: 'C-2291',
    case_status: 'OPEN',
    due_by: '2025-08-22T11:20:00+05:30',
  })

export const personalOfficerApproved = (): ClaimItem =>
  claim({
    claim_id: 'CL-000001',
    kind: 'PERSONAL',
    trigger_id: null,
    zone_id: null,
    decision_id: 'D-000002',
    outcome: 'APPROVED',
    amount_paise: 150_000,
    amount_label: '₹1,500',
    claim_at: T.slip,
    steps: steps(['completed', null, T.slip], ['completed', null, T.slip], ['completed', 'APPROVED', T.slip, ['अधिकारी ने मंज़ूर किया', 'Approved by an officer']], ['current'], ['pending']),
    case_id: 'C-2291',
    case_status: 'APPROVED',
    due_by: '2025-08-22T11:20:00+05:30',
  })

export const personalOfficerDeclined = (): ClaimItem =>
  claim({
    claim_id: 'CL-000001',
    kind: 'PERSONAL',
    trigger_id: null,
    zone_id: null,
    decision_id: 'D-000002',
    outcome: 'DECLINED',
    amount_paise: 0,
    amount_label: '₹0',
    claim_at: T.slip,
    steps: steps(['completed', null, T.slip], ['completed', null, T.slip], ['completed', 'DECLINED', T.slip, DECLINE], ['skipped'], ['skipped']),
    case_id: 'C-2291',
    case_status: 'DECLINED',
    due_by: '2025-08-22T11:20:00+05:30',
  })

/** The dispute card of the ₹1,380 payout: its own item, no steps, the amount of the payout. */
export const disputeOpen = (): ClaimItem =>
  claim({
    claim_id: null,
    disputed_claim_id: 'CL-000142',
    kind: 'DISPUTE',
    claim_at: '2025-08-19T17:12:00+05:30',
    trigger_id: null,
    steps: [],
    case_id: 'C-2291',
    case_status: 'OPEN',
    due_by: '2025-08-20T17:12:00+05:30',
  })

export const disputeClosed = (): ClaimItem => ({ ...disputeOpen(), case_status: 'CLOSED', resolution: 'Amount confirmed' })

export const withOutcome = (item: ClaimItem, outcome: DecisionOutcome): ClaimItem => ({ ...item, outcome })

/** A receipt that has been through the parser's shape: only the parts a test changes are spelled out. */
export type ReceiptPatch = { [K in keyof Receipt]?: Receipt[K] }
