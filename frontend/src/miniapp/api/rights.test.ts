/** Strict parsers of the rights routes: the examples of data-model 5.4 and 5.5 pass, and every broken shape is a contract violation. */
import { describe, expect, it } from 'vitest'

import { parseActivity, parseConsents, parseForget, parseGrievance, parseGrievances, parseWithdraw } from './rights'

const GRIEVANCE = {
  grievance_id: 'GR-000001',
  kind: 'DISPUTE',
  topic: 'PAYOUT_AMOUNT',
  respondent: 'INSURER',
  decision_id: 'D-000142',
  case_id: 'C-2291',
  status: 'OPEN',
  opened_at: '2025-08-19T17:12:00+05:30',
  current_step: 'PAYTM_DISPUTE',
  ladder_steps: [
    { level: 1, id: 'PAYTM_DISPUTE', name: 'Our claims officer', state: 'ACTIVE', delivery: 'IN_CHHATRI', entered_at: '2025-08-19T17:12:00+05:30', clock: { kind: 'OWN_SLA', hours: 24, due_by: '2025-08-20T17:12:00+05:30', state: 'RUNNING' } },
    { level: 2, id: 'INSURER_GRO', name: "The insurer's grievance officer", state: 'NOT_STARTED', delivery: 'SIMULATED', clock: { kind: 'TO_CONFIRM', note_en: 'Response time to be confirmed with the insurer' } },
    { level: 3, id: 'BIMA_BHAROSA', name: 'IRDAI Bima Bharosa portal', state: 'NOT_STARTED', delivery: 'SELF_REPORTED', clock: { kind: 'PORTAL_STATED', days: 14, started_at: null, statement_en: 'The portal says complaints are attended within 14 days' } },
  ],
  next_action: { id: 'ESCALATE_TO_INSURER_GRO', label_en: "Send this to the insurer's grievance officer" },
}

const consent = (purpose: string, extra: Record<string, unknown> = {}) => ({
  consent_id: 'CN-000002', purpose, purpose_label_en: 'a', purpose_label_hi: 'b', status: 'ACTIVE', granted_at: '2025-03-10T11:00:00+05:30', withdrawn_at: null,
  source: 'SEEDED', notice_version: null, current_notice_version: 'notice-1', required_to_buy: false, data_used_en: ['x'], data_used_hi: ['y'],
  withdraw_effect_en: 'e', withdraw_effect_hi: 'f', can_withdraw: true, blocked_reason: null, regrant_en: 'r', regrant_hi: 's', ...extra,
})
const THREE = [consent('SALES_DATA_FOR_CLAIM'), consent('SLIP_DATA_FOR_HOSPITAL_CLAIM', { held: [{ slip_id: 'MD-000002', claim_id: 'CL-000001', received_at: '2025-08-21T11:25:00+05:30', state: 'HELD', erased_at: null, can_erase: false, blocked_reason: 'case_open' }] }), consent('SETTLEMENT_DEDUCTION')]

describe('parseGrievance', () => {
  it('accepts the example of data-model 5.4', () => {
    const parsed = parseGrievance(GRIEVANCE)
    expect(parsed.ladder_steps.map((s) => s.clock.kind)).toEqual(['OWN_SLA', 'TO_CONFIRM', 'PORTAL_STATED'])
    expect(parsed.ladder_steps[1].entered_at).toBeNull()
    expect(parseGrievances([GRIEVANCE])).toHaveLength(1)
  })

  it.each([
    ['an unknown field', { ...GRIEVANCE, extra: 1 }],
    ['a topic outside the list', { ...GRIEVANCE, topic: 'ANGRY' }],
    ['a current step that is not on the ladder', { ...GRIEVANCE, current_step: 'OMBUDSMAN' }],
    ['a bad id', { ...GRIEVANCE, grievance_id: 'G-1' }],
    ['a clock with no source', { ...GRIEVANCE, ladder_steps: [{ ...GRIEVANCE.ladder_steps[0], clock: { kind: 'GUESS' } }] }],
    ['an empty ladder', { ...GRIEVANCE, ladder_steps: [] }],
  ])('rejects %s', (_name, body) => {
    expect(() => parseGrievance(body)).toThrow(/contract|:/)
  })
})

describe('parseConsents', () => {
  it('accepts the three purposes in order, with held slips on the slip item only', () => {
    const parsed = parseConsents(THREE)
    expect(parsed[1].held?.[0].slip_id).toBe('MD-000002')
    expect(parsed[0].held).toBeNull()
  })

  it('rejects a wrong order, a missing purpose, held slips on another purpose and a NOT_GIVEN record with an id', () => {
    expect(() => parseConsents([THREE[1], THREE[0], THREE[2]])).toThrow(/three purposes/)
    expect(() => parseConsents(THREE.slice(0, 2))).toThrow(/three purposes/)
    expect(() => parseConsents([consent('SALES_DATA_FOR_CLAIM', { held: [] }), THREE[1], THREE[2]])).toThrow(/only the slip item/)
    expect(() => parseConsents([consent('SALES_DATA_FOR_CLAIM', { status: 'NOT_GIVEN' }), THREE[1], THREE[2]])).toThrow(/NOT_GIVEN/)
  })
})

describe('the other parsers', () => {
  it('parses the withdrawal, the activity log and the erase result', () => {
    expect(parseWithdraw({ consent_id: 'CN-000002', purpose: 'SLIP_DATA_FOR_HOSPITAL_CLAIM', status: 'WITHDRAWN', withdrawn_at: '2025-08-21T12:00:00+05:30', action_taken_en: 'a', action_taken_hi: 'b', cover_status: 'ACTIVE' }).status).toBe('WITHDRAWN')
    const item = { seq: 146, at: '2025-08-19T17:00:00+05:30', purpose: 'SALES_DATA_FOR_CLAIM', kind: 'USED', text_en: 'a', text_hi: 'b', ref: { type: 'decision', id: 'D-000142' } }
    expect(parseActivity([item, { ...item, ref: null }])).toHaveLength(2)
    expect(() => parseActivity([{ ...item, kind: 'PEEKED' }])).toThrow(/:/)
    const forget = { slip_id: 'MD-000002', claim_id: 'CL-000001', erased_at: '2025-08-21T12:10:00+05:30', erased: { photo: true, claim_fields: true, decisions: 2, case_fields: 1, messages: 1 }, kept: ['AMOUNT'], audit_note_en: 'a', audit_note_hi: 'b' }
    expect(parseForget(forget).erased.decisions).toBe(2)
    expect(() => parseForget({ ...forget, erased: { ...forget.erased, decisions: -1 } })).toThrow(/:/)
  })
})
