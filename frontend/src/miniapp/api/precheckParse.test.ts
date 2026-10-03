import { describe, expect, it } from 'vitest'

import { ContractViolation } from './parse'
import { CONFIRMED_RESPONSE, NEEDS_TEAM_PRECHECK, READY_PRECHECK, RETAKE_PRECHECK } from './precheckFixtures'
import { parsePrecheck, parsePrecheckConfirm } from './precheckParse'

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
const mutate = (base: unknown, change: (draft: Record<string, unknown>) => void): unknown => {
  const draft = clone(base) as Record<string, unknown>
  change(draft)
  return draft
}

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

  it('rejects slots that are not the four in the fixed order, or whose state disagrees with the value', () => {
    expect(() => parsePrecheck(mutate(READY_PRECHECK, (d) => { (d.slots as unknown[]).pop() }))).toThrow(/four slots/)
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
})
