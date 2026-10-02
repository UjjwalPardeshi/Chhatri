/**
 * The strict view-model parsers (fs-04 section 6.5 and 9.4, data-model 5.1 and 5.8): unknown fields are rejected,
 * enums are checked and an impossible combination is a `contract_violation`. The valid cases are the contract's own
 * example files, so the parsers and the examples cannot drift apart.
 */
import { describe, expect, it } from 'vitest'

import { ApiError } from '../../api/client'
import { COVER_STATUSES } from '../../api/types'
import claimsDispute from '../../api/contract/claims.anil-dispute.json'
import claimsEmpty from '../../api/contract/claims.ramesh-empty.json'
import claimsPaid from '../../api/contract/claims.anil-paid.json'
import coverActive from '../../api/contract/cover.anil-active.json'
import coverNone from '../../api/contract/cover.ramesh-none.json'
import coverWaiting from '../../api/contract/cover.ramesh-waiting.json'
import premiumLink from '../../api/contract/premium-link.ramesh-blocked.json'
import receiptExample from '../../api/contract/receipt.anil-area.json'
import { ContractViolation, parseClaims, parseCover, parsePremiumLink, parseReceipt } from './parse'

/** A deep copy the test can edit: the parsers take unknown JSON, and the examples stay untouched. */
const copy = <T>(value: T): Record<string, unknown> => JSON.parse(JSON.stringify(value)) as Record<string, unknown>
const dataOf = (example: { response: { body: unknown } }): unknown => (example.response.body as { data: unknown }).data
const coverData = () => copy(dataOf(coverActive))
const claimsData = () => copy(dataOf(claimsPaid)) as unknown as Record<string, unknown>[]
const receiptData = () => copy(dataOf(receiptExample))

function violation(run: () => unknown): ContractViolation {
  let caught: unknown
  try {
    run()
  } catch (error) {
    caught = error
  }
  expect(caught, 'the parser should have raised a contract violation').toBeInstanceOf(ContractViolation)
  return caught as ContractViolation
}

describe('ContractViolation', () => {
  it('is an ApiError with the code contract_violation and names the field', () => {
    const error = violation(() => parseCover({ ...coverData(), status: 'MAYBE' }))
    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('contract_violation')
    expect(error.message).toContain('status')
  })
})

describe('parseCover', () => {
  it('accepts the six statuses and rejects an unknown field', () => {
    for (const status of COVER_STATUSES) {
      const data = { ...coverData(), status, cover_id: status === 'NONE' ? null : 'CV-0142' }
      expect(parseCover(data).status).toBe(status)
    }
    expect(violation(() => parseCover({ ...coverData(), surprise: 1 })).message).toContain('surprise')
    expect(violation(() => parseCover({ ...coverData(), status: 'PAUSED' })).message).toContain('status')
  })

  it('accepts the example files: an active cover, no cover and a cover waiting to start', () => {
    expect(parseCover(dataOf(coverActive))).toMatchObject({ status: 'ACTIVE', premium_per_day_label: '₹18.62', alert_id: 'A-20250818-01' })
    expect(parseCover(dataOf(coverNone))).toMatchObject({ status: 'NONE', cover_id: null, annual_limit_label: null })
    expect(parseCover(dataOf(coverWaiting))).toMatchObject({ status: 'WAITING', starts_on: '2025-08-25', prepaid_through: '2025-09-23' })
  })

  it('rejects a money label that is not the formatted paise, and a label without its paise', () => {
    expect(violation(() => parseCover({ ...coverData(), premium_per_day_label: '₹18.60' })).message).toContain('premium_per_day_label')
    expect(violation(() => parseCover({ ...coverData(), annual_limit_paise: null })).message).toContain('annual_limit')
  })

  it('rejects NONE with a cover id, and a cover with no id', () => {
    expect(violation(() => parseCover({ ...coverData(), status: 'NONE' })).message).toContain('cover_id')
    expect(violation(() => parseCover({ ...coverData(), cover_id: null })).message).toContain('cover_id')
  })

  it('rejects a body that is not an object, and a missing field', () => {
    expect(violation(() => parseCover(null)).message).toContain('cover')
    const { zone_name: _zone, ...rest } = coverData()
    expect(violation(() => parseCover(rest)).message).toContain('zone_name')
  })
})

describe('parseClaims', () => {
  it('accepts the example files: a paid claim, a dispute above it, and no claims', () => {
    expect(parseClaims(dataOf(claimsPaid))).toHaveLength(1)
    const items = parseClaims(dataOf(claimsDispute))
    expect(items.map((item) => item.kind)).toEqual(['DISPUTE', 'AREA'])
    expect(items[0]).toMatchObject({ claim_id: null, disputed_claim_id: 'CL-000142', steps: [], case_id: 'C-2291', amount_label: '₹1,380' })
    expect(parseClaims(dataOf(claimsEmpty))).toEqual([])
  })

  it('rejects an AREA item that is REFERRED', () => {
    const items = claimsData()
    items[0] = { ...items[0], outcome: 'REFERRED', case_id: 'C-2291', case_status: 'OPEN' }
    const error = violation(() => parseClaims(items))
    expect(error.message).toContain('AREA')
    expect(error.message).toContain('REFERRED')
  })

  it('rejects a REFERRED item with no case', () => {
    const items = claimsData()
    items[0] = { ...items[0], kind: 'PERSONAL', trigger_id: null, outcome: 'REFERRED' }
    expect(violation(() => parseClaims(items)).message).toContain('case_id')
  })

  it('rejects a DISPUTE item that carries steps, a claim id, or no case', () => {
    const base = copy(dataOf(claimsDispute)) as unknown as Record<string, unknown>[]
    const steps = (claimsData()[0].steps as unknown[]) ?? []
    expect(violation(() => parseClaims([{ ...base[0], steps }])).message).toContain('steps')
    expect(violation(() => parseClaims([{ ...base[0], claim_id: 'CL-000142' }])).message).toContain('claim_id')
    expect(violation(() => parseClaims([{ ...base[0], case_id: null }])).message).toContain('case_id')
  })

  it('rejects unknown fields, a step in the wrong order, and a lender code that is not a refusal', () => {
    const items = claimsData()
    expect(violation(() => parseClaims([{ ...items[0], extra: true }])).message).toContain('extra')
    const steps = items[0].steps as Record<string, unknown>[]
    expect(violation(() => parseClaims([{ ...items[0], steps: [steps[1], steps[0], ...steps.slice(2)] }])).message).toContain('steps')
    const coded = steps.map((step) => (step.name === 'EDI holiday' ? { ...step, reason_code: 'IN_ARREARS' } : step))
    expect(violation(() => parseClaims([{ ...items[0], steps: coded }])).message).toContain('reason_code')
    const stepWithExtra = steps.map((step, index) => (index === 0 ? { ...step, note: 'x' } : step))
    expect(violation(() => parseClaims([{ ...items[0], steps: stepWithExtra }])).message).toContain('note')
  })

  it('accepts a refused lender step with its code, and a declined claim with skipped steps', () => {
    const items = claimsData()
    const steps = (items[0].steps as Record<string, unknown>[]).map((step) =>
      step.name === 'EDI holiday' ? { ...step, result: 'REFUSED', reason_code: 'IN_ARREARS', reason_en: 'Not available. Your instalment is due as usual.' } : step,
    )
    expect(parseClaims([{ ...items[0], steps }])[0].steps[4]).toMatchObject({ result: 'REFUSED', reason_code: 'IN_ARREARS' })
    const declined = (items[0].steps as Record<string, unknown>[]).map((step) => {
      if (step.name === 'Decided') return { ...step, result: 'DECLINED' }
      if (step.name === 'Paid' || step.name === 'EDI holiday') return { ...step, status: 'skipped', result: null, at: null }
      return step
    })
    const parsed = parseClaims([{ ...items[0], outcome: 'DECLINED', amount_paise: 0, amount_label: '₹0', steps: declined }])
    expect(parsed[0].steps.map((step) => step.status)).toEqual(['completed', 'completed', 'completed', 'skipped', 'skipped'])
  })

  it('rejects a list that is not an array and an amount label that is not the formatted paise', () => {
    expect(violation(() => parseClaims({})).message).toContain('claims')
    const items = claimsData()
    expect(violation(() => parseClaims([{ ...items[0], amount_label: '₹1,379' }])).message).toContain('amount_label')
  })
})

describe('parseReceipt', () => {
  it('accepts the example: sources on every fact and check, one verified counterfactual', () => {
    const receipt = parseReceipt(dataOf(receiptExample))
    expect(receipt.decision).toMatchObject({ id: 'D-000142', amount_label: '₹1,380', decided_by: 'policy-engine' })
    expect(receipt.checks).toHaveLength(9)
    expect(receipt.explanation.facts.every((fact) => fact.sources.length > 0)).toBe(true)
    expect(receipt.counterfactuals[0]).toMatchObject({ kind: 'AMOUNT_SENSITIVITY', verified: true })
    expect(receipt.audit.hash_short).toHaveLength(12)
    expect(receipt.edi).toBeNull()
  })

  it('rejects a line without a source_ref', () => {
    const data = receiptData() as { explanation: { facts: { sources: unknown[] }[] } }
    data.explanation.facts[0].sources = []
    const error = violation(() => parseReceipt(data))
    expect(error.message).toContain('facts')
    expect(error.message).toContain('source')
    const noRef = receiptData() as { checks: { sources: Record<string, unknown>[] }[] }
    delete noRef.checks[0].sources[0].ref
    expect(violation(() => parseReceipt(noRef)).message).toContain('ref')
  })

  it('rejects a source with an extra field, an unknown kind, or an unknown origin', () => {
    const extra = receiptData() as { checks: { sources: Record<string, unknown>[] }[] }
    extra.checks[0].sources[0].detail = 'free text'
    expect(violation(() => parseReceipt(extra)).message).toContain('detail')
    const kind = receiptData() as { checks: { sources: Record<string, unknown>[] }[] }
    kind.checks[0].sources[0].kind = 'GUESS'
    expect(violation(() => parseReceipt(kind)).message).toContain('kind')
    const origin = receiptData() as { checks: { sources: Record<string, unknown>[] }[] }
    origin.checks[0].sources[0].origin = 'VERIFIED'
    expect(violation(() => parseReceipt(origin)).message).toContain('origin')
  })

  it('rejects an unverified counterfactual, an unknown field, and a bad audit prefix', () => {
    const unverified = receiptData() as { counterfactuals: Record<string, unknown>[] }
    unverified.counterfactuals[0].verified = false
    expect(violation(() => parseReceipt(unverified)).message).toContain('verified')
    expect(violation(() => parseReceipt({ ...receiptData(), notes: [] })).message).toContain('notes')
    const audit = receiptData() as { audit: Record<string, unknown> }
    audit.audit.hash_short = 'abc'
    expect(violation(() => parseReceipt(audit)).message).toContain('hash_short')
  })

  it('rejects a money label that is not the formatted paise', () => {
    const data = receiptData() as { decision: Record<string, unknown> }
    data.decision.amount_label = '₹1,38'
    expect(violation(() => parseReceipt(data)).message).toContain('amount_label')
  })

  it('accepts a receipt with a lender block, a case and a referred decision', () => {
    const data = receiptData() as Record<string, unknown>
    data.edi = { request_id: 'HR-000001', status: 'REFUSED', reason_code: 'NO_ALLOWANCE', instalment_date: '2025-08-20', instalment_label: '₹600', decided_at: '2025-08-19T17:05:00+05:30', lender: 'Simulated lender (NBFC partner)' }
    data.case = { id: 'C-2291', kind: 'DISPUTE', status: 'OPEN', due_by: '2025-08-20T17:12:00+05:30' }
    const parsed = parseReceipt(data)
    expect(parsed.edi).toMatchObject({ status: 'REFUSED', reason_code: 'NO_ALLOWANCE' })
    expect(parsed.case?.id).toBe('C-2291')
    data.edi = { ...(data.edi as Record<string, unknown>), status: 'GRANTED' }
    expect(violation(() => parseReceipt(data)).message).toContain('reason_code')
  })
})

describe('parsePremiumLink', () => {
  it('accepts the BLOCKED quote with its simulated link', () => {
    const result = parsePremiumLink(dataOf(premiumLink))
    expect(result.quote).toMatchObject({ outcome: 'BLOCKED', starts_on: '2025-08-25', first_payment_label: '₹424.80' })
    expect(result.premium).toMatchObject({ link_id: 'sim-7BFFBE', status: 'PENDING', source: 'simulated' })
  })

  it('accepts a quote with no link, and rejects an outcome that is not OK or BLOCKED', () => {
    const data = copy(dataOf(premiumLink)) as { quote: Record<string, unknown>; premium: unknown }
    expect(parsePremiumLink({ ...data, premium: null }).premium).toBeNull()
    expect(violation(() => parsePremiumLink({ ...data, quote: { ...data.quote, outcome: 'APPROVED' } })).message).toContain('outcome')
  })
})
