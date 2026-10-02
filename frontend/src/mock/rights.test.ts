/** Mock grievance, consent and evals routes (data-model 5.4, 5.5 and 5.10): flags, the router, the clocks, the 409s, the gates and the honest NOT MEASURED state. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Api } from '../api/endpoints'
import type { MockBackend } from './backend'
import { testApi } from './testkit'

let backend: MockBackend
beforeEach(() => vi.stubEnv('VITE_FEATURES', 'n5_grievances,n6_consents,h25_evals'))
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

async function setup(seek = '17:05') {
  const kit = testApi()
  backend = kit.backend
  await kit.api.seek(seek)
  const token = (await kit.api.session()).officer_token
  kit.client.setOfficerToken(token)
  return kit
}

/** The illness_mismatch scenario: Anil sends a slip whose name does not match, so a review case opens (C-2291). */
async function toReview(api: Api): Promise<void> {
  await api.load('illness_mismatch')
  await api.seek('11:20')
  await api.sendVoiceDemo('S-0142', 'ill')
  await api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
}

const open = (api: Api, topic: Parameters<Api['openGrievance']>[1]['topic'], text = 'मेरा नुकसान ज़्यादा हुआ।') => api.openGrievance('S-0142', { topic, text, lang: 'hi' })

describe('grievances', () => {
  it('are 404 while the flag is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = await setup()
    await expect(api.grievances('S-0142')).rejects.toMatchObject({ status: 404, code: 'not_found' })
  })

  it('starts with an empty list', async () => {
    const { api } = await setup()
    expect(await api.grievances('S-0142')).toEqual([])
  })

  it('opens a payout dispute at our claims officer with a 24 hour clock, the case and the chat lines', async () => {
    const { api, backend: b } = await setup()
    const grievance = await open(api, 'PAYOUT_AMOUNT')
    expect(grievance).toMatchObject({ grievance_id: 'GR-000001', kind: 'DISPUTE', respondent: 'INSURER', status: 'OPEN', current_step: 'PAYTM_DISPUTE' })
    expect(grievance.case_id).toMatch(/^C-\d+$/)
    expect(grievance.decision_id).toMatch(/^D-\d{6}$/)
    expect(grievance.ladder_steps.map((s) => s.id)).toEqual(['PAYTM_DISPUTE', 'INSURER_GRO', 'BIMA_BHAROSA', 'OMBUDSMAN'])
    expect(grievance.ladder_steps[0]).toMatchObject({ state: 'ACTIVE', delivery: 'IN_CHHATRI', clock: { kind: 'OWN_SLA', hours: 24, state: 'RUNNING' } })
    expect(grievance.ladder_steps[1].clock.kind).toBe('TO_CONFIRM')
    expect(grievance.ladder_steps[2].clock).toMatchObject({ kind: 'PORTAL_STATED', days: 14, started_at: null })
    expect(grievance.next_action?.id).toBe('ESCALATE_TO_INSURER_GRO')
    expect(b.runtime.cases.filter((c) => c.kind === 'DISPUTE')).toHaveLength(1)
    expect(b.runtime.messages.some((m) => m.kind === 'CASE_CHIP')).toBe(true)
  })

  it('makes no second case for a second tap on the same topic and decision', async () => {
    const { api, backend: b } = await setup()
    const first = await open(api, 'PAYOUT_AMOUNT')
    const second = await open(api, 'PAYOUT_AMOUNT')
    expect(second.grievance_id).toBe(first.grievance_id)
    expect(b.runtime.cases.filter((c) => c.kind === 'DISPUTE')).toHaveLength(1)
    expect(await api.grievances('S-0142')).toHaveLength(1)
  })

  it('routes the other topics by the fixed table and opens no case for them', async () => {
    const { api, backend: b } = await setup()
    expect(await open(api, 'EDI_HOLIDAY')).toMatchObject({ respondent: 'LENDER', current_step: 'LENDER_GRIEVANCE', case_id: null, kind: 'COMPLAINT' })
    expect(await open(api, 'APP_ISSUE')).toMatchObject({ respondent: 'PAYTM', current_step: 'PAYTM_SUPPORT' })
    expect(b.runtime.cases).toHaveLength(0)
  })

  it('refuses a payout dispute with no paid decision, a slow claim with no review, a bad topic and a long text', async () => {
    const { api } = await setup('08:00')
    await expect(open(api, 'PAYOUT_AMOUNT')).rejects.toMatchObject({ status: 422 })
    await expect(open(api, 'CLAIM_SLOW')).rejects.toMatchObject({ status: 422 })
    await expect(api.openGrievance('S-0142', { topic: 'OTHER', text: 'x'.repeat(501), lang: 'en' })).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
  })

  it('escalates one step at a time, records the filing date, and answers 409 for a wrong step', async () => {
    const { api } = await setup()
    const opened = await open(api, 'PAYOUT_AMOUNT')
    await expect(api.escalateGrievance('S-0142', opened.grievance_id, 'INSURER_GRO')).rejects.toMatchObject({ status: 409 })
    const gro = await api.escalateGrievance('S-0142', opened.grievance_id, 'PAYTM_DISPUTE')
    expect(gro.current_step).toBe('INSURER_GRO')
    expect(gro.ladder_steps.map((s) => s.state)).toEqual(['DONE', 'ACTIVE', 'NOT_STARTED', 'NOT_STARTED'])
    const bharosa = await api.escalateGrievance('S-0142', opened.grievance_id, 'INSURER_GRO', '2025-08-20')
    expect(bharosa.ladder_steps[2].clock).toMatchObject({ kind: 'PORTAL_STATED', started_at: '2025-08-20T00:00:00+05:30' })
    const last = await api.escalateGrievance('S-0142', opened.grievance_id, 'BIMA_BHAROSA', '2025-08-21')
    expect(last.current_step).toBe('OMBUDSMAN')
    expect(last.next_action).toBeNull()
    await expect(api.escalateGrievance('S-0142', opened.grievance_id, 'OMBUDSMAN')).rejects.toMatchObject({ status: 409 })
  })

  it('resolves, and then refuses to move on', async () => {
    const { api } = await setup()
    const opened = await open(api, 'PAYOUT_AMOUNT')
    const done = await api.resolveGrievance('S-0142', opened.grievance_id)
    expect(done.status).toBe('RESOLVED')
    expect(done.next_action).toBeNull()
    await expect(api.escalateGrievance('S-0142', opened.grievance_id, 'PAYTM_DISPUTE')).rejects.toMatchObject({ status: 409 })
  })

  it('writes audit entries with ids and codes, never the merchant text', async () => {
    const { api, backend: b } = await setup()
    await open(api, 'PAYOUT_AMOUNT', 'secret words of the merchant')
    const entry = b.runtime.audit.find((e) => e.action === 'grievance.open')
    expect(entry?.actor).toBe('merchant:S-0142')
    expect(JSON.stringify(b.runtime.audit)).not.toContain('secret words')
  })
})

describe('consents', () => {
  it('are 404 while the flag is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = await setup()
    await expect(api.consents('S-0142')).rejects.toMatchObject({ status: 404 })
  })

  it('lists three ACTIVE seeded purposes for Anil, in the fixed order, with the slip item holding its slips', async () => {
    const { api } = await setup()
    const list = await api.consents('S-0142')
    expect(list.map((c) => c.purpose)).toEqual(['SALES_DATA_FOR_CLAIM', 'SLIP_DATA_FOR_HOSPITAL_CLAIM', 'SETTLEMENT_DEDUCTION'])
    expect(list.every((c) => c.status === 'ACTIVE' && c.source === 'SEEDED' && c.notice_version === null)).toBe(true)
    expect(list.map((c) => c.required_to_buy)).toEqual([true, false, true])
    expect(list[0].withdraw_effect_en).toContain('wait 7 days')
    expect(list[2].withdraw_effect_en).toContain('22 August')
    expect(list[1].held).toEqual([])
    expect(list[0].held).toBeNull()
  })

  it('gives Ramesh three NOT_GIVEN placeholders', async () => {
    const { api } = await setup()
    const list = await api.consents('S-0907')
    expect(list.map((c) => c.status)).toEqual(['NOT_GIVEN', 'NOT_GIVEN', 'NOT_GIVEN'])
    expect(list.every((c) => c.consent_id === null)).toBe(true)
  })

  it('withdraws a purpose with the officer token, sends one chat line, and refuses twice', async () => {
    const { api, backend: b } = await setup()
    const slip = (await api.consents('S-0142'))[1]
    const result = await api.withdrawConsent('S-0142', slip.consent_id ?? '')
    expect(result).toMatchObject({ purpose: 'SLIP_DATA_FOR_HOSPITAL_CLAIM', status: 'WITHDRAWN', cover_status: 'ACTIVE' })
    expect(result.action_taken_en).toBe(slip.withdraw_effect_en)
    expect((await api.consents('S-0142'))[1]).toMatchObject({ status: 'WITHDRAWN', can_withdraw: false })
    expect(b.runtime.messages.at(-1)?.text_en).toContain('you turned off slip reading')
    await expect(api.withdrawConsent('S-0142', slip.consent_id ?? '')).rejects.toMatchObject({ status: 409, code: 'already_withdrawn' })
  })

  it('cancels the cover on a sales withdrawal, and writes it to the activity log with a fixed sentence', async () => {
    const { api } = await setup()
    const sales = (await api.consents('S-0142'))[0]
    expect((await api.withdrawConsent('S-0142', sales.consent_id ?? '')).cover_status).toBe('CANCELLED')
    const log = await api.consentActivity('S-0142')
    expect(log.items.map((i) => i.kind)).toEqual(['EFFECT', 'WITHDRAWN', ...log.items.slice(2).map((i) => i.kind)])
    expect(log.items[1].text_en).toBe('You turned off: Use my sales data to decide claims and set my premium.')
  })

  it('refuses a sales withdrawal while a personal-claim review is open', async () => {
    const { api } = await setup()
    await toReview(api)
    const list = await api.consents('S-0142')
    expect(list[0]).toMatchObject({ can_withdraw: false, blocked_reason: 'case_open' })
    await expect(api.withdrawConsent('S-0142', list[0].consent_id ?? '')).rejects.toMatchObject({ status: 409, code: 'case_open' })
    expect(list[1].held?.[0]).toMatchObject({ state: 'HELD', can_erase: false, blocked_reason: 'case_open' })
  })

  it('needs the officer token for the two writes', async () => {
    const kit = testApi()
    backend = kit.backend
    await kit.api.seek('17:05')
    const slip = (await kit.api.consents('S-0142'))[1]
    await expect(kit.api.withdrawConsent('S-0142', slip.consent_id ?? '')).rejects.toMatchObject({ status: 401 })
  })

  it('filters and pages the activity log', async () => {
    const { api } = await setup()
    const all = await api.consentActivity('S-0142')
    expect(all.items.length).toBeGreaterThan(0)
    expect(all.items.every((i) => i.purpose === 'SALES_DATA_FOR_CLAIM')).toBe(true)
    const none = await api.consentActivity('S-0142', { purpose: 'SETTLEMENT_DEDUCTION' })
    expect(none).toEqual({ items: [], total: 0 })
    const page = await api.consentActivity('S-0142', { limit: 1, offset: 0 })
    expect(page.items).toHaveLength(1)
    expect(page.total).toBe(all.total)
  })
})

async function withClosedReview() {
  const kit = await setup()
  await toReview(kit.api)
  const review = kit.backend.runtime.cases.find((c) => c.kind === 'PERSONAL_CLAIM_REVIEW')
  await kit.api.approve(review?.id ?? '', 'ok')
  return kit
}

describe('forget my slip', () => {
  it('erases a slip after the review is answered, keeps the decision, and says the log cannot be edited', async () => {
    const { api } = await withClosedReview()
    const held = (await api.consents('S-0142'))[1].held?.[0]
    expect(held).toMatchObject({ state: 'HELD', can_erase: true })
    const result = await api.forgetSlip('S-0142', held?.slip_id ?? '')
    expect(result.erased).toMatchObject({ photo: true, claim_fields: true })
    expect(result.kept).toContain('DECISION_OUTCOME')
    expect(result.audit_note_en).toContain('cannot be edited')
    expect((await api.consents('S-0142'))[1].held?.[0]).toMatchObject({ state: 'ERASED', can_erase: false })
    await expect(api.forgetSlip('S-0142', held?.slip_id ?? '')).rejects.toMatchObject({ status: 409, code: 'already_erased' })
    expect((await api.consentActivity('S-0142', { purpose: 'SLIP_DATA_FOR_HOSPITAL_CLAIM' })).items.some((i) => i.kind === 'ERASED')).toBe(true)
  })

  it('refuses while the review is open and for an unknown slip', async () => {
    const { api } = await setup()
    await toReview(api)
    const held = (await api.consents('S-0142'))[1].held?.[0]
    await expect(api.forgetSlip('S-0142', held?.slip_id ?? '')).rejects.toMatchObject({ status: 409, code: 'case_open' })
    await expect(api.forgetSlip('S-0142', 'MD-009999')).rejects.toMatchObject({ status: 404 })
  })
})

describe('GET /api/evals/summary', () => {
  it('is 404 while the flag is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = await setup()
    await expect(api.evalsSummary()).rejects.toMatchObject({ status: 404 })
  })

  it('answers the no-run state: six suites in the plan order, every one NOT_MEASURED, no number anywhere', async () => {
    const { api } = await setup()
    const summary = await api.evalsSummary()
    expect(summary).toMatchObject({ measured: false, run: null })
    expect(summary.suites.map((s) => s.id)).toEqual(['intent', 'guard', 'ask', 'slips', 'voice', 'chain'])
    expect(summary.suites.every((s) => s.status === 'NOT_MEASURED' && s.reason === 'no run stored' && s.metrics.length === 0)).toBe(true)
  })
})
