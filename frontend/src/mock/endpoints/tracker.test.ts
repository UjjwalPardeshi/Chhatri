/** Mock GET /api/merchants/{id}/claims: the five steps of fs-04 section 9.5 built from decisions, payouts, pauses and cases. */
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ClaimItem, ScenarioName } from '../../api/types'
import { parseClaims } from '../../miniapp/api/parse'
import type { MockBackend } from '../backend'
import { MOCK_OFFICER_TOKEN } from '../fixtures'
import { testApi } from '../testkit'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

async function session(scenario: ScenarioName, at: string) {
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load(scenario)
  await kit.api.seek(at)
  return kit
}

const statuses = (item: ClaimItem) => item.steps.map((s) => s.status)

async function claimsOf(api: Awaited<ReturnType<typeof session>>['api'], id = 'S-0142') {
  const { items, meta } = await api.claims(id)
  expect(parseClaims(items)).toEqual(items)
  return { items, meta }
}

describe('area claim', () => {
  it('has all five steps done for Anil at 17:05, with the catalogue lines', async () => {
    const { api } = await session('monsoon', '17:05')
    const { items, meta } = await claimsOf(api)
    expect(meta).toEqual({ total: 1, limit: 1, offset: 0 })
    expect(items[0]).toMatchObject({
      claim_id: 'CL-000142',
      disputed_claim_id: null,
      kind: 'AREA',
      claim_at: '2025-08-19T17:00:00+05:30',
      zone_id: 'Z7',
      trigger_id: 'E-Z7-20250819',
      decision_id: 'D-000142',
      outcome: 'APPROVED',
      amount_paise: 138_000,
      amount_label: '₹1,380',
      case_id: null,
      case_status: null,
      due_by: null,
      resolution: null,
    })
    expect(statuses(items[0])).toEqual(['completed', 'completed', 'completed', 'completed', 'completed'])
    expect(items[0].steps.map((s) => s.name)).toEqual(['Detected', 'Checked', 'Decided', 'Paid', 'EDI holiday'])
    expect(items[0].steps.map((s) => s.result)).toEqual([null, null, 'APPROVED', null, 'GRANTED'])
    expect(items[0].steps.map((s) => s.at?.slice(11, 16))).toEqual(['17:00', '17:00', '17:00', '17:04', '17:05'])
    expect(items[0].steps.map((s) => s.reason_en)).toEqual([
      "Your area's sales fell 63% during the alert.",
      'All 9 checks passed.',
      'How your payout was worked out: ½ × ₹4,380 × 63% = ₹1,380',
      "Credited with today's settlement",
      "Tomorrow's ₹600 instalment is paused.",
    ])
    expect(items[0].steps.map((s) => s.reason_hi)).toEqual([
      'अलर्ट के दौरान आपके इलाके की बिक्री 63% गिरी।',
      'सभी 9 जाँचें पास हुईं।',
      'आपके भुगतान का हिसाब: ₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380',
      'आज के सेटलमेंट के साथ जमा',
      'कल की ₹600 की किस्त रोक दी गई है।',
    ])
    expect(items[0].steps.every((s) => s.reason_code === null)).toBe(true)
  })

  it('shows the credit as the current step until it lands, then the lender as asked', async () => {
    const { api } = await session('monsoon', '17:00')
    let item = (await claimsOf(api)).items[0]
    expect(statuses(item)).toEqual(['completed', 'completed', 'completed', 'current', 'pending'])
    expect(item.steps[3].at).toBeNull()
    await api.seek('17:04')
    item = (await claimsOf(api)).items[0]
    expect(statuses(item)).toEqual(['completed', 'completed', 'completed', 'completed', 'current'])
    expect(item.steps[4]).toMatchObject({ result: null, at: null })
  })

  it('has no claim before the trigger and none for a merchant without cover', async () => {
    const { api } = await session('monsoon', '16:59')
    expect(await claimsOf(api)).toEqual({ items: [], meta: { total: 0, limit: 0, offset: 0 } })
    const { api: buy } = await session('buy_cover', '18:00')
    expect((await claimsOf(buy, 'S-0907')).items).toEqual([])
  })

  it('answers 404 for an unknown merchant', async () => {
    const { api } = await session('monsoon', '17:05')
    await expect(api.claims('S-9999')).rejects.toMatchObject({ code: 'not_found', message: 'merchant S-9999 not found' })
  })
})

describe('dispute', () => {
  it('is a separate card above the claim, with the case and its 24 hour clock, steps empty', async () => {
    const { api } = await session('monsoon', '17:12')
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    const { items, meta } = await claimsOf(api)
    expect(meta?.total).toBe(2)
    expect(items.map((i) => i.kind)).toEqual(['DISPUTE', 'AREA'])
    expect(items[0]).toEqual({
      claim_id: null,
      disputed_claim_id: 'CL-000142',
      kind: 'DISPUTE',
      claim_at: '2025-08-19T17:12:00+05:30',
      zone_id: 'Z7',
      trigger_id: null,
      decision_id: 'D-000142',
      outcome: 'APPROVED',
      amount_paise: 138_000,
      amount_label: '₹1,380',
      steps: [],
      case_id: 'C-2291',
      case_status: 'OPEN',
      due_by: '2025-08-20T17:12:00+05:30',
      resolution: null,
    })
  })

  it('closes with the officer note and the amount unchanged', async () => {
    const { api } = await session('monsoon', '17:12')
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    await api.approve('C-2291', 'Amount confirmed')
    const dispute = (await claimsOf(api)).items[0]
    expect(dispute).toMatchObject({ kind: 'DISPUTE', case_status: 'CLOSED', resolution: 'Amount confirmed', amount_label: '₹1,380', outcome: 'APPROVED' })
  })

  it('is left out when there is no paid decision to dispute', async () => {
    const { api } = await session('monsoon', '09:00')
    await api.sendText('S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    expect((await claimsOf(api)).items).toEqual([])
  })
})

describe('personal claim', () => {
  it('is APPROVED and paid for the clean slip, with no steps skipped', async () => {
    const { api, backend: b } = await session('illness', '11:20')
    await api.sendSampleSlip('S-0142', 'anil_admission_slip.png')
    b.step(5)
    const item = (await claimsOf(api)).items[0]
    expect(item).toMatchObject({ claim_id: 'CL-000001', kind: 'PERSONAL', trigger_id: null, zone_id: null, outcome: 'APPROVED', amount_label: '₹1,500', case_id: null })
    expect(statuses(item)).toEqual(['completed', 'completed', 'completed', 'completed', 'completed'])
    expect(item.steps[0].at?.slice(11, 16)).toBe('11:20')
  })

  it('is REFERRED to a claims officer for the mismatched slip, with the case and its clock', async () => {
    const { api } = await session('illness_mismatch', '11:20')
    await api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
    const item = (await claimsOf(api)).items[0]
    expect(item).toMatchObject({ kind: 'PERSONAL', outcome: 'REFERRED', case_id: 'C-2291', case_status: 'OPEN', due_by: '2025-08-22T11:20:00+05:30', resolution: null })
    expect(statuses(item)).toEqual(['completed', 'completed', 'current', 'pending', 'pending'])
    expect(item.steps[2].result).toBe('REFERRED')
  })

  it('shows one claim, paid, after the officer approves the referral', async () => {
    const { api, backend: b } = await session('illness_mismatch', '11:20')
    await api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
    await api.approve('C-2291', '')
    b.step(5)
    const { items } = await claimsOf(api)
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ outcome: 'APPROVED', case_status: 'APPROVED', amount_label: '₹1,500' })
    expect(statuses(items[0])).toEqual(['completed', 'completed', 'completed', 'completed', 'completed'])
    expect(items[0].decision_id).toBe(b.runtime.decisions.at(-1)?.id)
  })

  it('is not paid, and skips Paid and the EDI holiday, after the officer declines', async () => {
    const { api } = await session('illness_mismatch', '11:20')
    await api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
    await api.decline('C-2291', '')
    const item = (await claimsOf(api)).items[0]
    expect(item).toMatchObject({ outcome: 'DECLINED', amount_label: '₹0', case_status: 'DECLINED' })
    expect(statuses(item)).toEqual(['completed', 'completed', 'completed', 'skipped', 'skipped'])
    expect(item.steps[2]).toMatchObject({ result: 'DECLINED', reason_en: "The name on the slip doesn't match your KYC, so this claim can't be approved." })
  })
})

async function lenderSession(forced: boolean) {
  vi.stubEnv('VITE_FEATURES', 'x4_lender_request')
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load('monsoon')
  backend.runtime.lenderForced = forced
  await kit.api.seek('17:05')
  return kit
}

describe('EDI holiday step with x4_lender_request on (the lender decides, fs-03 7.5)', () => {
  it('names the lender when the lender grants', async () => {
    const { api } = await lenderSession(false)
    const { items } = await claimsOf(api)
    expect(items[0].steps[4]).toMatchObject({
      status: 'completed',
      result: 'GRANTED',
      reason_code: null,
      reason_en: "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty.",
    })
    expect(items[0].steps[4].at?.slice(11, 16)).toBe('17:05')
  })

  it('is completed with NO_RESPONSE, and says the instalment is due, when the lender gives no answer', async () => {
    const { api } = await lenderSession(true)
    const { items } = await claimsOf(api)
    expect(items[0].steps[4]).toMatchObject({
      status: 'completed',
      result: 'NO_RESPONSE',
      reason_en: 'We could not reach your lender. Your instalment is due as usual.',
      reason_hi: 'हम आपके लेंडर तक नहीं पहुँच सके। आपकी किस्त हमेशा की तरह देय है।',
    })
  })
})
