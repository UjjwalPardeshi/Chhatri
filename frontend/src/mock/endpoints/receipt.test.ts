/** Mock GET /api/decisions/{id}/receipt: sources on every number, counterfactuals the mock engine re-ran, DEMO.md numbers. */
import { afterEach, describe, expect, it } from 'vitest'

import type { Receipt, ScenarioName, Source } from '../../api/types'
import { parseReceipt } from '../../miniapp/api/parse'
import type { MockBackend } from '../backend'
import { createMockFetch } from '../fetch'
import { MOCK_OFFICER_TOKEN } from '../fixtures'
import { testApi } from '../testkit'

let backend: MockBackend
afterEach(() => backend?.dispose())

async function session(scenario: ScenarioName, at: string) {
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load(scenario)
  await kit.api.seek(at)
  return kit
}

async function receiptOf(api: Awaited<ReturnType<typeof session>>['api'], id: string): Promise<Receipt> {
  const receipt = await api.receipt(id)
  expect(parseReceipt(receipt)).toEqual(receipt)
  return receipt
}

const allSources = (r: Receipt): Source[] => [
  ...r.explanation.facts.flatMap((f) => f.sources),
  ...r.checks.flatMap((c) => c.sources),
  ...r.counterfactuals.flatMap((c) => c.sources),
]

describe('the receipt of Anil\'s area payout (D-000142)', () => {
  it('carries the decision, the formula and the five money facts, each with a source', async () => {
    const { api } = await session('monsoon', '17:05')
    const r = await receiptOf(api, 'D-000142')
    expect(r.decision).toEqual({
      id: 'D-000142',
      claim_id: 'CL-000142',
      merchant_id: 'S-0142',
      outcome: 'APPROVED',
      amount_paise: 138_000,
      amount_label: '₹1,380',
      rules_version: 'pilot-0.1',
      decided_at: '2025-08-19T17:00:00+05:30',
      decided_by: 'policy-engine',
      supersedes: null,
      referral_reason: null,
    })
    expect(r.explanation).toMatchObject({ formula_en: '½ × ₹4,380 × 63% = ₹1,380', formula_hi: '₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380', clause: 'C4' })
    expect(r.explanation.facts.map((f) => [f.key, f.value])).toEqual([
      ['expected_day', '₹4,380'],
      ['area_index', '37%'],
      ['drop_pct', '63%'],
      ['share', 'half'],
      ['cap', '₹2,500'],
      ['amount', '₹1,380'],
    ])
    expect(r.explanation.facts[0].label_en).toBe('Your usual Tuesday')
    expect(r.explanation.facts.every((f) => f.sources.length > 0)).toBe(true)
    expect(r.explanation.facts[0].sources[0]).toEqual({
      kind: 'FORECAST',
      label: 'Your usual day, worked out from your past sales',
      ref: 'forecast:S-0142:2025-08-19',
      as_of: '2025-08-19T17:00:00+05:30',
      origin: 'SIMULATED',
      clause: 'C4',
    })
  })

  it('has the nine area checks in order, each with a clause and sources', async () => {
    const { api } = await session('monsoon', '17:05')
    const r = await receiptOf(api, 'D-000142')
    expect(r.checks.map((c) => [c.code, c.clause])).toEqual([
      ['COVER_IN_FORCE', 'C5'],
      ['PREMIUM_PREPAID', 'C6'],
      ['COVER_BEFORE_ALERT', 'C5'],
      ['ALERT_ACTIVE', 'C2'],
      ['INDEX_QUORUM', 'C2'],
      ['BELOW_FLOOR', 'C2'],
      ['BELOW_MODEL_RANGE', 'C2'],
      ['NOT_ALREADY_PAID', 'C7'],
      ['WITHIN_ANNUAL_LIMIT', 'C4'],
    ])
    expect(r.checks.every((c) => c.severity === 'HARD' && c.status === 'PASS' && !c.erased && c.sources.length > 0)).toBe(true)
    const alert = r.checks.find((c) => c.code === 'ALERT_ACTIVE')
    expect(alert).toMatchObject({ label_en: 'Alert active for the whole window', observed: 'A-20250818-01 19 Aug 2025 14:00–19 Aug 2025 20:00' })
    expect(alert?.sources[0]).toMatchObject({ kind: 'ALERT', ref: 'alert:A-20250818-01', as_of: '2025-08-18T17:30:00+05:30', origin: 'SIMULATED' })
    expect(r.checks[0].sources.map((s) => s.ref)).toEqual(['cover:CV-0142', 'rules:pilot-0.1:cover.waiting_period_days'])
  })

  it('names only SIMULATED or CONFIG origins: nothing is LIVE in the mock', async () => {
    const { api } = await session('monsoon', '17:05')
    const origins = new Set(allSources(await receiptOf(api, 'D-000142')).map((s) => s.origin))
    expect([...origins].toSorted()).toEqual(['CONFIG', 'SIMULATED'])
  })

  it('has one counterfactual from re-running the engine: a 64% drop pays ₹1,402', async () => {
    const { api } = await session('monsoon', '17:05')
    const { counterfactuals } = await receiptOf(api, 'D-000142')
    expect(counterfactuals).toHaveLength(1)
    expect(counterfactuals[0]).toMatchObject({
      id: 'CF-1',
      kind: 'AMOUNT_SENSITIVITY',
      actionable: false,
      changes: [{ check_code: null, field: 'drop_pct', observed: '63', needed: '64' }],
      result: { outcome: 'APPROVED', amount_paise: 140_200, amount_label: '₹1,402' },
      verified: true,
      text_en: 'One more point of area drop would have added about ₹22.',
      text_hi: 'इलाके की गिरावट एक प्रतिशत और होती, तो लगभग ₹22 और जुड़ते।',
    })
    expect(counterfactuals[0].sources[0]).toMatchObject({ kind: 'SALES_INDEX', ref: 'trigger:E-Z7-20250819' })
  })

  it('has the credited payout, the audit position and the grievance ladder; the lender block waits for X4', async () => {
    const { api, backend: b } = await session('monsoon', '17:05')
    const r = await receiptOf(api, 'D-000142')
    expect(r.payout).toEqual({ id: 'P-000142', status: 'CREDITED', amount_label: '₹1,380', credited_at: '2025-08-19T17:04:00+05:30' })
    expect(r.edi).toBeNull()
    expect(r.case).toBeNull()
    const entry = b.runtime.audit.find((e) => e.action === 'decision.made' && e.subject_id === 'D-000142')
    expect(r.audit).toEqual({ seq: entry?.seq, hash_short: entry?.hash.slice(0, 12), verify_path: '/api/audit/verify' })
    expect(r.grievance).toEqual({ dispute_allowed: true, ladder: ['PAYTM_DISPUTE', 'INSURER_GRO', 'BIMA_BHAROSA', 'OMBUDSMAN'], first_step_hours: 24 })
  })

  it('shows the credit as pending, and no dispute yet, before the settlement lands', async () => {
    const { api } = await session('monsoon', '17:00')
    const r = await receiptOf(api, 'D-000142')
    expect(r.payout).toMatchObject({ status: 'PENDING', credited_at: null })
    expect(r.grievance.dispute_allowed).toBe(false)
  })

  it('points at the dispute case once Anil says his loss was bigger', async () => {
    const { api } = await session('monsoon', '17:12')
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    expect((await receiptOf(api, 'D-000142')).case).toEqual({ id: 'C-2291', kind: 'DISPUTE', status: 'OPEN', due_by: '2025-08-20T17:12:00+05:30' })
  })
})

describe('personal claims', () => {
  it('explains the referral of the mismatched slip and what would have flipped it', async () => {
    const { api } = await session('illness_mismatch', '11:20')
    await api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
    const r = await receiptOf(api, 'D-000001')
    expect(r.decision).toMatchObject({ outcome: 'REFERRED', amount_label: '₹1,500', claim_id: 'CL-000001' })
    expect(r.decision.referral_reason).toContain('NAME_MATCHES_KYC')
    expect(r.checks).toHaveLength(9)
    expect(r.checks.find((c) => c.code === 'NAME_MATCHES_KYC')).toMatchObject({ severity: 'SOFT', status: 'FAIL', clause: 'C3' })
    expect(r.checks.find((c) => c.code === 'NAME_MATCHES_KYC')?.sources.map((s) => s.kind)).toEqual(['SLIP', 'KYC', 'RULES'])
    expect(r.counterfactuals).toHaveLength(1)
    expect(r.counterfactuals[0]).toMatchObject({
      kind: 'FLIP_FROM_REFERRED',
      actionable: false,
      changes: [{ check_code: 'NAME_MATCHES_KYC', field: 'slip_name_score', observed: '41', needed: '85 or more' }],
      result: { outcome: 'APPROVED', amount_paise: 150_000, amount_label: '₹1,500' },
      verified: true,
      text_en: 'If the name on the slip had matched your KYC name (score 85 or more), this claim would have been paid automatically.',
    })
    expect(r.payout).toBeNull()
    expect(r.case).toMatchObject({ id: 'C-2291', kind: 'PERSONAL_CLAIM_REVIEW', status: 'OPEN' })
    expect(r.grievance.dispute_allowed).toBe(false)
  })

  it('carries one more day as the sensitivity of the approved illness claim', async () => {
    const { api, backend: b } = await session('illness', '11:20')
    await api.sendSampleSlip('S-0142', 'anil_admission_slip.png')
    b.step(5)
    const r = await receiptOf(api, 'D-000001')
    expect(r.decision).toMatchObject({ outcome: 'APPROVED', amount_label: '₹1,500' })
    expect(r.counterfactuals).toHaveLength(1)
    expect(r.counterfactuals[0]).toMatchObject({
      kind: 'AMOUNT_SENSITIVITY',
      changes: [{ check_code: null, field: 'days', observed: '1', needed: '2' }],
      result: { outcome: 'APPROVED', amount_paise: 300_000, amount_label: '₹3,000' },
      text_en: 'Each extra qualifying day adds ₹1,500, up to 3 days without a review.',
    })
    expect(r.explanation.facts.map((f) => f.key)).toEqual(['expected_day', 'share', 'cap', 'days', 'amount'])
    expect(r.payout).toMatchObject({ status: 'CREDITED', amount_label: '₹1,500' })
    expect(r.grievance.dispute_allowed).toBe(true)
  })

  it('has the officer decision superseding the referral, with no counterfactual of its own', async () => {
    const { api } = await session('illness_mismatch', '11:20')
    await api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
    await api.approve('C-2291', '')
    const r = await receiptOf(api, 'D-000002')
    expect(r.decision).toMatchObject({ outcome: 'APPROVED', decided_by: 'officer:officer', supersedes: 'D-000001', referral_reason: null })
    expect(r.checks.filter((c) => c.severity === 'SOFT').every((c) => c.status === 'WAIVED_BY_OFFICER')).toBe(true)
    expect(r.counterfactuals).toEqual([])
    expect(r.case).toMatchObject({ id: 'C-2291', status: 'APPROVED' })
  })
})

describe('errors', () => {
  it('answers 404 for a well-formed id that does not exist', async () => {
    const { api } = await session('monsoon', '17:05')
    await expect(api.receipt('D-999999')).rejects.toMatchObject({ code: 'not_found', status: 404, message: 'decision D-999999 not found' })
  })

  it('answers 422 with the field for a malformed id', async () => {
    const { backend: b } = await session('monsoon', '17:05')
    const res = await createMockFetch(b)('/api/decisions/D-12/receipt')
    expect(res.status).toBe(422)
    expect(await res.json()).toMatchObject({ ok: false, error: { code: 'validation_error', message: 'invalid request', fields: { decision_id: expect.any(String) } } })
  })
})
