import { describe, expect, it } from 'vitest'

import { ContractViolation } from './parse'
import { ASKED_CONSENT, AWAITING_CONSENT_RESPONSE, CONFIRMED_RESPONSE, DOCTOR_PENDING_RESPONSE, NEEDS_TEAM_PRECHECK, OPEN_READY, READY_PRECHECK, RETAKE_PRECHECK } from './precheckFixtures'
import { parsePrecheck, parsePrecheckConfirm, parsePrecheckOpen } from './precheckParse'

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
const mutate = (base: unknown, change: (draft: Record<string, unknown>) => void): unknown => {
  const draft = clone(base) as Record<string, unknown>
  change(draft)
  return draft
}

const slotValue = (index: number, value: string) => mutate(READY_PRECHECK, (d) => { (d.slots as { value: unknown }[])[index].value = value })

describe('parsePrecheck', () => {
  it('accepts the READY, RETAKE and NEEDS_TEAM examples of data-model 5.3', () => {
    expect(parsePrecheck(READY_PRECHECK)).toEqual(READY_PRECHECK)
    expect(parsePrecheck(RETAKE_PRECHECK)).toEqual(RETAKE_PRECHECK)
    expect(parsePrecheck(NEEDS_TEAM_PRECHECK)).toEqual(NEEDS_TEAM_PRECHECK)
  })

  it('accepts the Hindi label the real backend adds to the slip source, and still rejects any other extra field', () => {
    const real = mutate(READY_PRECHECK, (d) => { (d.source as Record<string, unknown>).label_hi = 'अस्पताल की पर्ची, जैसी पढ़ी गई' })
    expect(parsePrecheck(real)).toEqual(READY_PRECHECK)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.source as Record<string, unknown>).label_hi = '' }))).toThrow(/label_hi/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.source as Record<string, unknown>).label_fr = 'x' }))).toThrow(/unknown field label_fr/)
  })

  it('rejects a body that is not an object, an unknown field and a missing field', () => {
    expect(() => parsePrecheck(null)).toThrow(ContractViolation)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.extra = 1 }))).toThrow(/unknown field extra/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { delete d.gate }))).toThrow(/missing field gate/)
  })

  it('rejects a status or a reason outside the closed lists', () => {
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.status = 'APPROVED' }))).toThrow(ContractViolation)
    expect(() => parsePrecheck(mutate(RETAKE_PRECHECK, (d) => { d.reason = 'BLURRY' }))).toThrow(ContractViolation)
  })

  it('reads the six slots in order, the doctor and the registration number last', () => {
    expect(parsePrecheck(READY_PRECHECK).slots.map((slot) => slot.key)).toEqual(['patient_name', 'admission_date', 'discharge_date', 'hospital_name', 'doctor_name', 'doctor_registration_no'])
    expect(parsePrecheck(READY_PRECHECK).slots[5].value).toBe('MMC-2011-45817')
  })

  it('caps the doctor at 80 characters and the registration number at 32, and keeps them plain text', () => {
    expect(parsePrecheck(slotValue(4, 'D'.repeat(80))).slots[4].value).toHaveLength(80)
    expect(() => parsePrecheck(slotValue(4, 'D'.repeat(81)))).toThrow(/too long/)
    expect(() => parsePrecheck(slotValue(5, '1'.repeat(33)))).toThrow(/too long/)
    expect(() => parsePrecheck(slotValue(5, 'call +91 98200 00000'))).toThrow(/plain text/)
  })

  it('accepts the doctor retake (DOCTOR_MISSING with SLIP_RETAKE_DOCTOR)', () => {
    const doctor = mutate(RETAKE_PRECHECK, (d) => {
      d.reason = 'DOCTOR_MISSING'
      d.guidance = { key: 'SLIP_RETAKE_DOCTOR', text_hi: 'डॉक्टर का नाम साफ़ नहीं दिख रहा।', text_en: 'The doctor is not clear.' }
    })
    expect(parsePrecheck(doctor).reason).toBe('DOCTOR_MISSING')
  })

  it('rejects slots that are not the six in the fixed order, or whose state disagrees with the value', () => {
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.slots as unknown[]).pop() }))).toThrow(/six slots/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.slots = (d.slots as unknown[]).slice(0, 4) }))).toThrow(/six slots/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.slots as unknown[]).reverse() }))).toThrow(ContractViolation)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.slots as { value: unknown }[])[0].value = null }))).toThrow(/READ/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.slots as { state: unknown }[])[0].state = 'NOT_ON_SLIP' }))).toThrow(ContractViolation)
  })

  it('rejects markup or a diagnosis-like extra slot in a value (plain text only)', () => {
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.slots as { value: unknown }[])[0].value = '<script>x</script>' }))).toThrow(/plain text/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.slots as { value: unknown }[])[1].value = 'approved' }))).toThrow(/date/)
  })

  it('rejects a READY check that carries a reason, guidance or the wrong button', () => {
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.reason = 'LOW_CONFIDENCE' }))).toThrow(ContractViolation)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.next_action = { kind: 'SEND_TO_TEAM', label_hi: 'x', label_en: 'x' } }))).toThrow(/READY/)
  })

  it('rejects a RETAKE or NEEDS_TEAM check with no reason or guidance, or the wrong button', () => {
    expect(() => parsePrecheck(mutate(RETAKE_PRECHECK, (d) => { d.reason = null }))).toThrow(ContractViolation)
    expect(() => parsePrecheck(mutate(RETAKE_PRECHECK, (d) => { d.guidance = null }))).toThrow(ContractViolation)
    expect(() => parsePrecheck(mutate(NEEDS_TEAM_PRECHECK, (d) => { (d.next_action as { kind: unknown }).kind = 'CONFIRM_FIELDS' }))).toThrow(ContractViolation)
  })

  it('rejects an id that does not look like one, a retake count out of range and a source that is not the slip', () => {
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.precheck_id = 'PC-1' }))).toThrow(ContractViolation)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.retakes_left = 3 }))).toThrow(/retakes_left/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.source as { kind: unknown }).kind = 'RULE' }))).toThrow(/SLIP/)
  })

  it('rejects a SIMULATED answer that names a live provider (an honest label)', () => {
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.provider = 'gemini' }))).toThrow(/SIMULATED/)
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { d.mode = 'LIVE' }))).toThrow(/LIVE/)
  })
})

describe('parsePrecheckConfirm', () => {
  it('accepts the confirm example', () => {
    expect(parsePrecheckConfirm(CONFIRMED_RESPONSE)).toEqual(CONFIRMED_RESPONSE)
  })

  it('needs a case id when the claim was referred and none when it was approved', () => {
    expect(() => parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, outcome: 'REFERRED' })).toThrow(/case_id/)
    expect(() => parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, case_id: 'C-2291' })).toThrow(/case_id/)
    expect(parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, outcome: 'REFERRED', case_id: 'C-2291', confirmed_as: 'SENT_TO_TEAM' }).case_id).toBe('C-2291')
  })

  it('rejects an unknown outcome, a bad claim id and an unknown field', () => {
    expect(() => parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, outcome: 'PAID' })).toThrow(ContractViolation)
    expect(() => parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, claim_id: 'X' })).toThrow(ContractViolation)
    expect(() => parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, extra: 1 })).toThrow(ContractViolation)
  })

  it('reads a server without the doctor keys as no consent and no doctor check (the rule off)', () => {
    const { consent: _consent, doctor_check: _check, ...old } = CONFIRMED_RESPONSE
    expect(parsePrecheckConfirm(old)).toEqual(CONFIRMED_RESPONSE)
  })

  it('accepts AWAITING_CONSENT with nothing filed and the question ASKED', () => {
    expect(parsePrecheckConfirm(AWAITING_CONSENT_RESPONSE)).toEqual(AWAITING_CONSENT_RESPONSE)
    expect(() => parsePrecheckConfirm({ ...AWAITING_CONSENT_RESPONSE, claim_id: 'CL-000001' })).toThrow(/AWAITING_CONSENT/)
    expect(() => parsePrecheckConfirm({ ...AWAITING_CONSENT_RESPONSE, consent: null })).toThrow(/consent/)
    expect(() => parsePrecheckConfirm({ ...AWAITING_CONSENT_RESPONSE, consent: { ...ASKED_CONSENT, status: 'GIVEN', answered_at: '2025-08-21T11:21:00+05:30' } })).toThrow(/ASKED/)
  })

  it('needs a claim, a decision and an outcome once CONFIRMED', () => {
    expect(() => parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, claim_id: null })).toThrow(/CONFIRMED/)
    expect(() => parsePrecheckConfirm({ ...CONFIRMED_RESPONSE, outcome: null })).toThrow(/CONFIRMED/)
  })

  it('accepts REFERRED with no case while the doctor is being asked', () => {
    expect(parsePrecheckConfirm(DOCTOR_PENDING_RESPONSE)).toEqual(DOCTOR_PENDING_RESPONSE)
    expect(() => parsePrecheckConfirm({ ...DOCTOR_PENDING_RESPONSE, doctor_check: null })).toThrow(/case_id/)
  })

  it('rejects an unknown key or purpose in the consent block', () => {
    expect(() => parsePrecheckConfirm({ ...AWAITING_CONSENT_RESPONSE, consent: { ...ASKED_CONSENT, phone: '9820000000' } })).toThrow(/unknown field phone/)
    expect(() => parsePrecheckConfirm({ ...AWAITING_CONSENT_RESPONSE, consent: { ...ASKED_CONSENT, purpose: 'SALES_DATA_FOR_CLAIM' } })).toThrow(/purpose/)
    expect(() => parsePrecheckConfirm({ ...DOCTOR_PENDING_RESPONSE, doctor_check: { ...DOCTOR_PENDING_RESPONSE.doctor_check, chat_id: 'tg:1' } })).toThrow(/unknown field chat_id/)
  })
})

describe('parsePrecheckOpen', () => {
  it('accepts an open READY pre-check, a waiting question and a closed check-in', () => {
    expect(parsePrecheckOpen(OPEN_READY)).toEqual(OPEN_READY)
    const waiting = { ...OPEN_READY, precheck: null, awaiting_consent: ASKED_CONSENT }
    expect(parsePrecheckOpen(waiting)).toEqual(waiting)
    const closed = { merchant_id: 'S-0142', checkin_open: false, first_silent_day: null, precheck: null, awaiting_consent: null }
    expect(parsePrecheckOpen(closed)).toEqual(closed)
  })

  it('rejects an unknown key, a closed check-in with a pre-check, and both a pre-check and a question', () => {
    expect(() => parsePrecheckOpen({ ...OPEN_READY, extra: 1 })).toThrow(/unknown field extra/)
    expect(() => parsePrecheckOpen({ ...OPEN_READY, checkin_open: false, first_silent_day: null })).toThrow(/checkin_open/)
    expect(() => parsePrecheckOpen({ ...OPEN_READY, awaiting_consent: ASKED_CONSENT })).toThrow(/awaiting_consent/)
  })
})
