/** The mock lender (X4, fs-03 sections 7 and 8): Chhatri asks, the lender answers, only a grant pauses anything. */
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from './backend'
import { inboundPhoto, inboundVoiceDemo } from './conversation'
import type { MockRuntime } from './runtime'
import { testBackend } from './testkit'
import { zonePanelView } from './views'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

const FLAG = 'x4_lender_request'
const GRANTED_LINE = "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty."
const NO_ANSWER_LINE = 'We could not reach your lender about the ₹600 instalment due tomorrow, so it is due as usual. Your payout is not affected.'

function storm(time: string, features = FLAG, forced = false): MockRuntime {
  vi.stubEnv('VITE_FEATURES', features)
  backend = testBackend()
  backend.runtime.lenderForced = forced
  backend.seek(time)
  return backend.runtime
}

const instalmentActions = (rt: MockRuntime) => rt.audit.map((e) => e.action).filter((a) => a.startsWith('instalment.'))
const lastLine = (rt: MockRuntime, merchantId: string) => rt.messages.filter((m) => m.merchant_id === merchantId).at(-1)?.text_en

describe('the mock lender grants by default', () => {
  it('asks once, is granted, and writes request, answer and pause to the audit chain in that order', () => {
    const rt = storm('17:05')
    expect(instalmentActions(rt)).toEqual(['instalment.holiday_request', 'instalment.holiday_decision', 'instalment.pause'])
    expect(rt.holidayRequests).toHaveLength(1)
    expect(rt.pauses).toHaveLength(1)
    expect(rt.holidayRequests[0].instalment_date).toBe(rt.pauses[0].instalment_date)
    expect(lastLine(rt, 'S-0142')).toBe(GRANTED_LINE)
  })

  it('sends only what the lender needs: no claim kind, no reason, no payout amount', () => {
    const rt = storm('17:05')
    const asked = rt.audit.find((e) => e.action === 'instalment.holiday_request')
    expect(asked).toMatchObject({ actor: 'workflow:payout', subject_type: 'holiday_request', subject_id: 'HR-000001' })
    expect(Object.keys(asked?.data ?? {}).toSorted()).toEqual(['amount_paise', 'decision_id', 'instalment_date', 'lender', 'loan_id', 'merchant_id', 'payout_id'])
    expect(asked?.data.amount_paise).toBe(60_000)
    const answered = rt.audit.find((e) => e.action === 'instalment.holiday_decision')
    expect(answered?.data).toMatchObject({ decision: 'GRANTED', reason_code: null, moved_to: 'end of tenure', penalty_paise: 0, lender: 'Simulated lender (NBFC partner)' })
  })

  it('still reports the storm numbers: the KPI counts grants only and Z7 stays at ₹58,900', () => {
    const rt = storm('17:05')
    expect(rt.kpis).toMatchObject({ shops_paid: 312, instalments_paused: 123 })
    const z7 = rt.zones.find((z) => z.id === 'Z7')
    if (!z7) throw new Error('Z7 missing')
    expect(zonePanelView(rt, z7).rows.at(-1)).toEqual({ label: 'Total', value: '₹58,900 · instalments paused' })
  })

  it('asks for a personal claim too and counts the grant', () => {
    vi.stubEnv('VITE_FEATURES', FLAG)
    backend = testBackend()
    backend.load('illness')
    backend.seek('11:20')
    inboundVoiceDemo(backend.runtime, 'S-0142', 'ill')
    inboundPhoto(backend.runtime, 'S-0142', '/slips/anil_admission_slip.png', 'anil_admission_slip.png')
    backend.step(5)
    const rt = backend.runtime
    expect(rt.holidayRequests).toHaveLength(1)
    expect(rt.holidayRequests[0]).toMatchObject({ status: 'GRANTED', decision_id: 'D-000001', payout_id: 'P-000001' })
    expect(rt.kpis.instalments_paused).toBe(1)
    expect(lastLine(rt, 'S-0142')).toMatch(/^Your lender has paused tomorrow's ₹600 instalment\./)
  })
})

describe('the request waits for a credited payout (G2)', () => {
  it('asks nobody and audits the skip when the payout is not credited by the time the step runs', () => {
    const rt = storm('17:04')
    rt.payouts = rt.payouts.map((p) => ({ ...p, status: 'FAILED' as const }))
    backend.step(1)
    expect(rt.holidayRequests).toEqual([])
    expect(rt.pauses).toEqual([])
    expect(instalmentActions(rt)).toEqual(['instalment.holiday_skipped'])
    expect(rt.audit.find((e) => e.action === 'instalment.holiday_skipped')?.data).toMatchObject({ merchant_id: 'S-0142', reason: 'PAYOUT_NOT_CREDITED', payout_status: 'FAILED' })
  })
})

describe('a forced lender gives no answer', () => {
  it('records NO_RESPONSE, pauses nothing, leaves the payout credited and tells the merchant', () => {
    const rt = storm('17:05', FLAG, true)
    expect(rt.holidayRequests[0]).toMatchObject({ status: 'NO_RESPONSE', reason_code: null, decided_at: '2025-08-19T17:05:00+05:30' })
    expect(rt.pauses).toEqual([])
    expect(rt.payouts[0]).toMatchObject({ status: 'CREDITED', amount_label: '₹1,380' })
    expect(instalmentActions(rt)).toEqual(['instalment.holiday_request', 'instalment.holiday_decision'])
    expect(lastLine(rt, 'S-0142')).toBe(NO_ANSWER_LINE)
  })

  it('counts no paused instalments in the KPI, the zone total or the feed', () => {
    const rt = storm('17:05', FLAG, true)
    expect(rt.kpis).toMatchObject({ shops_paid: 312, instalments_paused: 0 })
    const z7 = rt.zones.find((z) => z.id === 'Z7')
    if (!z7) throw new Error('Z7 missing')
    expect(zonePanelView(rt, z7).rows.at(-1)).toEqual({ label: 'Total', value: '₹58,900' })
    expect(rt.feed.filter((f) => f.type === 'instalment')).toEqual([])
  })
})

describe('with the flag off the BUILT pause is unconditional', () => {
  it('never asks the lender and keeps the old line, the old numbers and the pause entry', () => {
    const rt = storm('17:05', '')
    expect(rt.holidayRequests).toEqual([])
    expect(instalmentActions(rt)).toEqual(['instalment.pause'])
    expect(rt.pauses).toHaveLength(1)
    expect(rt.kpis.instalments_paused).toBe(123)
    expect(lastLine(rt, 'S-0142')).toBe("Tomorrow's ₹600 instalment is paused.")
  })

  it('is not changed by a forced lender (nobody is asked)', () => {
    const rt = storm('17:05', '', true)
    expect(rt.holidayRequests).toEqual([])
    expect(rt.kpis.instalments_paused).toBe(123)
  })
})
