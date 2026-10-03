/**
 * Mock parity for the slip pre-check routes (data-model 5.3 and 6, card 4.2, design 2.3 and 2.4): same bodies, ids,
 * statuses, the doctor question between the confirm and the claim, the open route and the 409 codes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import type { ScenarioName } from '../api/types'
import { parsePrecheck, parsePrecheckConfirm, parsePrecheckOpen } from '../miniapp/api/precheckParse'
import type { MockBackend } from './backend'
import { MOCK_OFFICER_TOKEN } from './fixtures'
import { testApi } from './testkit'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})
beforeEach(() => vi.stubEnv('VITE_FEATURES', 'n3_slip_precheck'))

async function session(scenario: ScenarioName = 'illness', at = '11:30') {
  const kit = testApi()
  backend = kit.backend
  await kit.api.load(scenario)
  await kit.api.seek(at)
  return kit
}

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    return error as ApiError
  }
  throw new Error('expected the call to fail')
}

describe('POST slip-precheck', () => {
  it('answers 404 not_found for both routes while the flag is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = await session()
    const read = await failure(api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' }))
    expect([read.status, read.code]).toEqual([404, 'not_found'])
    const confirm = await failure(api.confirmSlipPrecheck('S-0142', 'PC-000001', 'CONFIRM'))
    expect([confirm.status, confirm.code]).toEqual([404, 'not_found'])
  })

  it('reads the sample slip and decides nothing', async () => {
    const { api, backend: b } = await session()
    const check = await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png', lang: 'hi' })
    expect(parsePrecheck(check)).toEqual(check)
    expect(check).toMatchObject({ precheck_id: 'PC-000001', status: 'READY', attempt: 1, retakes_left: 2, mode: 'SIMULATED', provider: 'mock', fallback_reason: 'MOCK_BACKEND' })
    expect(check.slots[0]).toEqual({ key: 'patient_name', value: 'Anil R. Jadhav', state: 'READ', note: null })
    expect(check.slots[2]).toMatchObject({ key: 'discharge_date', state: 'NOT_ON_SLIP' })
    expect(check.slots.slice(4)).toEqual([
      { key: 'doctor_name', value: 'Dr S. Rao', state: 'READ', note: null },
      { key: 'doctor_registration_no', value: 'MMC-2011-45817', state: 'READ', note: null },
    ])
    expect(check.source).toMatchObject({ kind: 'SLIP', origin: 'SIMULATED', clause: 'C3' })
    expect(b.runtime.decisions.filter((d) => d.merchant_id === 'S-0142')).toHaveLength(0)
  })

  it('an empty body uses the scenario sample', async () => {
    const { api } = await session('illness_mismatch')
    const check = await api.client.post<unknown>('/api/merchants/S-0142/slip-precheck', {})
    expect(parsePrecheck(check).slots[0].value).toBe('Sunil Pawar')
  })

  it('a blurry slip is a RETAKE with one reason and the clear-photo guidance', async () => {
    const { api } = await session()
    const check = await api.slipPrecheck('S-0142', { sample: 'blurry_slip.png' })
    expect(parsePrecheck(check)).toEqual(check)
    expect(check).toMatchObject({ status: 'RETAKE', reason: 'LOW_CONFIDENCE', next_action: { kind: 'RETAKE_PHOTO' } })
    expect(check.guidance?.key).toBe('SLIP_RETAKE_CLEAR')
    expect(check.checklist.every((line) => line.state === 'WARN')).toBe(true)
  })

  it('the third photo that is not ready goes to the team with the photo limit, and a fourth is refused', async () => {
    const { api } = await session()
    await api.slipPrecheck('S-0142', { sample: 'blurry_slip.png' })
    const second = await api.slipPrecheck('S-0142', { sample: 'blurry_slip.png' })
    expect([second.attempt, second.retakes_left, second.status]).toEqual([2, 1, 'RETAKE'])
    const third = await api.slipPrecheck('S-0142', { sample: 'blurry_slip.png' })
    expect(parsePrecheck(third)).toEqual(third)
    expect(third).toMatchObject({ attempt: 3, retakes_left: 0, status: 'NEEDS_TEAM', reason: 'LOW_CONFIDENCE', next_action: { kind: 'SEND_TO_TEAM' } })
    expect(third.guidance?.key).toBe('SLIP_PHOTO_LIMIT')
    const fourth = await failure(api.slipPrecheck('S-0142', { sample: 'blurry_slip.png' }))
    expect([fourth.status, fourth.code]).toEqual([409, 'photo_limit'])
  })

  it('a photo that is not a sample reads as unreadable, and a bad sample name is 404', async () => {
    const { api } = await session()
    const bad = await failure(api.slipPrecheck('S-0142', { sample: 'nope.png' }))
    expect([bad.status, bad.code]).toEqual([404, 'not_found'])
    const odd = await api.slipPrecheck('S-0142', { file: new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 1, 2, 3, 4])], 'mine.png', { type: 'image/png' }) })
    expect(odd.status).toBe('RETAKE')
  })

  it('is 409 no_checkin with no silence check-in open, and 404 for an unknown merchant', async () => {
    const early = await session('illness', '10:45')
    const conflict = await failure(early.api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' }))
    expect([conflict.status, conflict.code]).toEqual([409, 'no_checkin'])
    const missing = await failure(early.api.slipPrecheck('S-9999', { sample: 'anil_admission_slip.png' }))
    expect([missing.status, missing.code]).toEqual([404, 'not_found'])
  })

  it('writes audit rows with ids and codes, never a slip value', async () => {
    const { api, backend: b } = await session()
    await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' })
    const shown = b.runtime.audit.find((e) => e.action === 'precheck.shown')
    expect(shown?.data).toMatchObject({ precheck_id: 'PC-000001', status: 'READY', attempt: 1 })
    expect(JSON.stringify(shown)).not.toContain('Jadhav')
  })
})

describe('POST slip-precheck confirm', () => {
  it('CONFIRM on READY files nothing yet: it asks the doctor question once, as a chat message with Yes and No', async () => {
    const { api, backend: b } = await session()
    const check = await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' })
    const asked = await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONFIRM')
    expect(parsePrecheckConfirm(asked)).toEqual(asked)
    expect(asked).toMatchObject({ status: 'AWAITING_CONSENT', confirmed_as: 'FIELDS_CONFIRMED', claim_id: null, outcome: null })
    expect(asked.consent).toMatchObject({ purpose: 'doctor_verification', status: 'ASKED', doctor_name: 'Dr S. Rao', hospital_name: 'KEM Hospital, Parel' })
    expect(asked.consent?.question_en).toBe('May we ask Dr S. Rao at KEM Hospital, Parel to confirm your visit? They will see only your name and the date.')
    expect(asked.messages).toHaveLength(1)
    const card = asked.messages[0].card as unknown as { consent_for: string; actions: { kind: string }[] }
    expect([card.consent_for, card.actions.map((a) => a.kind)]).toEqual([check.precheck_id, ['CONSENT_YES', 'CONSENT_NO']])
    expect(asked.messages[0].meta).toMatchObject({ precheck_id: check.precheck_id, consent_purpose: 'doctor_verification' })
    expect(b.runtime.decisions.filter((d) => d.merchant_id === 'S-0142')).toHaveLength(0)
  })

  it('CONSENT_YES records the answer, files the claim and the engine pays after the (simulated) doctor confirms', async () => {
    const { api, backend: b } = await session()
    const check = await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' })
    await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONFIRM')
    const done = await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONSENT_YES')
    expect(parsePrecheckConfirm(done)).toEqual(done)
    expect(done).toMatchObject({ status: 'CONFIRMED', confirmed_as: 'FIELDS_CONFIRMED', outcome: 'APPROVED', case_id: null, doctor_check: null })
    expect(done.consent).toMatchObject({ status: 'GIVEN' })
    expect(done.messages.map((m) => m.meta.doctor_check)).toContain('CONFIRMED')
    expect(b.runtime.decisions.find((d) => d.id === done.decision_id)?.checks.find((c) => c.code === 'DOCTOR_CONFIRMED')?.status).toBe('PASS')
    const consent = b.runtime.audit.find((e) => e.action === 'consent.granted')
    expect(consent?.data).toMatchObject({ purpose: 'DOCTOR_CONFIRMATION', precheck_id: check.precheck_id })
    expect(JSON.stringify(consent)).not.toMatch(/Jadhav|Rao/)
  })

  it('CONSENT_NO records the refusal, files the claim, and a person decides it', async () => {
    const { api, backend: b } = await session()
    const check = await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' })
    await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONFIRM')
    const done = await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONSENT_NO')
    expect(parsePrecheckConfirm(done)).toEqual(done)
    expect(done).toMatchObject({ status: 'CONFIRMED', outcome: 'REFERRED' })
    expect(done.consent).toMatchObject({ status: 'REFUSED' })
    expect(done.case_id).toMatch(/^C-\d+$/)
    expect(b.runtime.audit.some((e) => e.action === 'consent.refused' && e.data.purpose === 'DOCTOR_CONFIRMATION')).toBe(true)
  })

  it('a confirmed READ whose name does not match is REFERRED with a case and its messages', async () => {
    const { api } = await session('illness_mismatch')
    const check = await api.slipPrecheck('S-0142', { sample: 'mismatch_admission_slip.png' })
    await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONFIRM')
    const done = await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONSENT_YES')
    expect(parsePrecheckConfirm(done)).toEqual(done)
    expect(done.outcome).toBe('REFERRED')
    expect(done.case_id).toMatch(/^C-\d+$/)
    expect(done.messages.map((m) => m.kind)).toEqual(['TEXT', 'CASE_CHIP'])
  })

  it('SEND_TO_TEAM on a RETAKE files the claim as referred, with no doctor question', async () => {
    const { api } = await session()
    const check = await api.slipPrecheck('S-0142', { sample: 'blurry_slip.png' })
    const done = await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'SEND_TO_TEAM')
    expect(done).toMatchObject({ confirmed_as: 'SENT_TO_TEAM', outcome: 'REFERRED', consent: null })
    expect(done.case_id).not.toBeNull()
  })

  it('answers each wrong action with its 409 code (design 2.3)', async () => {
    const { api } = await session()
    const code = async (id: string, action: Parameters<typeof api.confirmSlipPrecheck>[2]) => (await failure(api.confirmSlipPrecheck('S-0142', id, action))).code
    const blurry = await api.slipPrecheck('S-0142', { sample: 'blurry_slip.png' })
    expect(await code(blurry.precheck_id, 'CONFIRM')).toBe('not_ready')
    expect(await code(blurry.precheck_id, 'CONSENT_YES')).toBe('no_consent_question')
    const ready = await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' })
    expect(await code(blurry.precheck_id, 'SEND_TO_TEAM')).toBe('superseded')
    expect(await code(ready.precheck_id, 'SEND_TO_TEAM')).toBe('ready_not_team')
    expect(await code(ready.precheck_id, 'CONSENT_NO')).toBe('no_consent_question')
    await api.confirmSlipPrecheck('S-0142', ready.precheck_id, 'CONFIRM')
    expect(await code(ready.precheck_id, 'CONFIRM')).toBe('consent_pending')
    await api.confirmSlipPrecheck('S-0142', ready.precheck_id, 'CONSENT_YES')
    expect(await code(ready.precheck_id, 'CONSENT_YES')).toBe('already_confirmed')
    expect((await failure(api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' }))).code).toBe('no_checkin')
  })

  it('is 404 for an unknown pre-check and 422 for an unknown action', async () => {
    const { api } = await session()
    const check = await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' })
    expect((await failure(api.confirmSlipPrecheck('S-0142', 'PC-000099', 'CONFIRM'))).status).toBe(404)
    const bad = await failure(api.client.post<unknown>(`/api/merchants/S-0142/slip-precheck/${check.precheck_id}/confirm`, { action: 'APPROVE' }))
    expect([bad.status, bad.code]).toEqual([422, 'validation_error'])
  })
})

describe('GET slip-precheck/open', () => {
  it('says whether a check-in waits, then shows the open pre-check, then the waiting question, then nothing', async () => {
    const { api } = await session()
    expect(parsePrecheckOpen(await api.openSlipPrecheck('S-0142'))).toMatchObject({ checkin_open: true, first_silent_day: '2025-08-20', precheck: null, awaiting_consent: null })
    const check = await api.slipPrecheck('S-0142', { sample: 'anil_admission_slip.png' })
    expect((await api.openSlipPrecheck('S-0142')).precheck?.precheck_id).toBe(check.precheck_id)
    await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONFIRM')
    expect(await api.openSlipPrecheck('S-0142')).toMatchObject({ precheck: null, awaiting_consent: { status: 'ASKED', precheck_id: check.precheck_id } })
    await api.confirmSlipPrecheck('S-0142', check.precheck_id, 'CONSENT_YES')
    expect(await api.openSlipPrecheck('S-0142')).toEqual({ merchant_id: 'S-0142', checkin_open: false, first_silent_day: null, precheck: null, awaiting_consent: null })
  })

  it('is closed before the check-in and 404 while the flag is off', async () => {
    const early = await session('illness', '10:45')
    expect((await early.api.openSlipPrecheck('S-0142')).checkin_open).toBe(false)
    vi.stubEnv('VITE_FEATURES', '')
    expect((await failure(early.api.openSlipPrecheck('S-0142'))).status).toBe(404)
  })
})

async function withoutSlipConsent() {
  const kit = await session()
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  const slip = (await kit.api.consents('S-0142'))[1]
  await kit.api.withdrawConsent('S-0142', slip.consent_id ?? '')
  return kit
}

describe('the slip gate with n6_consents on (fs-07 9.3, N6-T11)', () => {
  beforeEach(() => vi.stubEnv('VITE_FEATURES', 'n3_slip_precheck,n6_consents'))

  it('reads the slip under the seeded ACTIVE slip consent, as before', async () => {
    const { api } = await session()
    expect(parsePrecheck(await api.slipPrecheck('S-0142', {})).status).toBe('READY')
  })

  it('answers 409 consent_required and reads nothing when the slip consent is off and no OK is sent', async () => {
    const { api } = await withoutSlipConsent()
    const error = await failure(api.slipPrecheck('S-0142', {}))
    expect([error.status, error.code]).toEqual([409, 'consent_required'])
    expect(backend.runtime.audit.some((e) => e.action === 'precheck.shown')).toBe(false)
  })

  it('records the OK given with the photo (SLIP_UPLOAD), then reads the slip', async () => {
    const { api } = await withoutSlipConsent()
    const check = parsePrecheck(await api.slipPrecheck('S-0142', { consent: true, notice_version: 'notice-1' }))
    expect(check.status).toBe('READY')
    expect((await api.consents('S-0142'))[1]).toMatchObject({ status: 'ACTIVE', source: 'SLIP_UPLOAD', notice_version: 'notice-1' })
    expect(backend.runtime.audit.filter((e) => e.action === 'consent.granted').map((e) => e.data)).toEqual([expect.objectContaining({ purpose: 'SLIP_DATA_FOR_HOSPITAL_CLAIM', source: 'SLIP_UPLOAD' })])
  })

  it('refuses an OK given under an old notice', async () => {
    const { api } = await withoutSlipConsent()
    expect((await failure(api.slipPrecheck('S-0142', { consent: true, notice_version: 'notice-0' }))).code).toBe('consent_required')
  })
})
