/**
 * Mock GET /api/decisions/{decision_id}/receipt (data-model 5.8, fs-09 section 10): the decision, the formula and the
 * money facts, every check with its clause and sources, the counterfactuals the engine re-ran, the payout, the case,
 * the audit position and the grievance ladder. It is built from the mock decision, payout and case records. The
 * lender block (`edi`) is the lender's request for the decision and stays null while none was made (X4 off, or no loan), as the backend sends it. Like the
 * backend, the receipt carries no phone number.
 */
import type { Case, Decision, Receipt } from '../../api/types'
import { POLICY_RULES } from '../fixtures'
import { invalid, merchantById, notFound, ok, type Route } from '../http'
import type { MockRuntime } from '../runtime'
import { counterfactualsFor } from './counterfactual'
import { AMOUNT_CLAUSE, CHECK_CLAUSES, checkSources, explanationOf, moneyFacts, type Provenance } from './provenance'

const DECISION_ID = /^D-\d{6,}$/
/** The grievance steps in order (fs-06 section 5.4); the first one's clock is the dispute SLA. */
const GRIEVANCE_LADDER = ['PAYTM_DISPUTE', 'INSURER_GRO', 'BIMA_BHAROSA', 'OMBUDSMAN']

/** The case of this decision: a dispute names the decision it is about, a referral follows the claim through the officer's decision. */
function caseOf(rt: MockRuntime, decision: Decision): Case | null {
  return (
    rt.cases.find((c) => c.decision?.id === decision.id) ??
    rt.cases.find((c) => c.kind !== 'DISPUTE' && c.decision?.claim_id === decision.claim_id) ??
    null
  )
}

/** The lender's request for this decision (X4): None while no request was made (no loan, or the flag is off). */
function ediOf(rt: MockRuntime, decision: Decision): Receipt['edi'] {
  const request = rt.holidayRequests.filter((r) => r.decision_id === decision.id).at(-1)
  if (!request) return null
  return {
    request_id: request.id,
    status: request.status,
    reason_code: request.reason_code,
    instalment_date: request.instalment_date,
    instalment_label: request.instalment_label,
    decided_at: request.decided_at,
    lender: request.lender,
  }
}

function auditOf(rt: MockRuntime, decision: Decision): Receipt['audit'] {
  const entry = rt.audit.find((e) => e.action === 'decision.made' && e.subject_id === decision.id)
  if (!entry) throw new Error(`no audit entry for decision ${decision.id}`)
  return { seq: entry.seq, hash_short: entry.hash.slice(0, 12), verify_path: '/api/audit/verify' }
}

export function receiptView(rt: MockRuntime, decisionId: string): Receipt {
  const decision = rt.decisions.find((d) => d.id === decisionId)
  if (!decision) throw notFound(`decision ${decisionId}`)
  const merchant = merchantById(decision.merchant_id)
  const provenance: Provenance = { rt, merchant, decision }
  const payout = rt.payouts.find((p) => p.decision_id === decision.id) ?? null
  const kase = caseOf(rt, decision)
  const explanation = explanationOf(decision)
  return {
    decision: {
      id: decision.id,
      claim_id: decision.claim_id,
      merchant_id: decision.merchant_id,
      outcome: decision.outcome,
      amount_paise: decision.amount_paise,
      amount_label: decision.amount_label,
      rules_version: decision.rules_version,
      decided_at: decision.decided_at,
      decided_by: decision.decided_by,
      supersedes: decision.supersedes,
      referral_reason: decision.referral_reason,
    },
    explanation: { formula_en: explanation.formula_en, formula_hi: explanation.formula_hi, clause: AMOUNT_CLAUSE, facts: moneyFacts(provenance) },
    checks: decision.checks.map((c) => ({
      code: c.code,
      severity: c.severity,
      status: c.status,
      label_en: c.label_en,
      detail_en: c.detail_en,
      observed: c.observed,
      required: c.required,
      clause: CHECK_CLAUSES[c.code] ?? null,
      erased: false,
      sources: checkSources(c.code, provenance),
    })),
    counterfactuals: counterfactualsFor(provenance),
    payout: payout ? { id: payout.id, status: payout.status, amount_label: payout.amount_label, credited_at: payout.credited_at } : null,
    edi: ediOf(rt, decision),
    case: kase ? { id: kase.id, kind: kase.kind, status: kase.status, due_by: kase.due_by } : null,
    audit: auditOf(rt, decision),
    grievance: {
      dispute_allowed: decision.outcome === 'APPROVED' && payout?.status === 'CREDITED',
      ladder: GRIEVANCE_LADDER,
      first_step_hours: POLICY_RULES.dispute_sla_hours,
    },
  }
}

export const RECEIPT_ROUTES: readonly Route[] = [
  {
    method: 'GET',
    pattern: /^\/api\/decisions\/(D-\d+)\/receipt$/,
    handler: (c) => {
      if (!DECISION_ID.test(c.params[0])) throw invalid('decision_id', 'must look like D-000142')
      return ok(receiptView(c.backend.runtime, c.params[0]))
    },
  },
]
