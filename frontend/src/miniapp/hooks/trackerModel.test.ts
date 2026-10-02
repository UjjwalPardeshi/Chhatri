/** The claim tracker model of fs-04 section 9.5: the five steps for each situation, built from what the API recorded. */
import { describe, expect, it } from 'vitest'

import type { ClaimItem } from '../../api/types'
import {
  areaCreditPending,
  areaDeclined,
  areaLenderAsked,
  areaLenderGranted,
  areaLenderRefused,
  areaNoLoan,
  claim,
  disputeClosed,
  disputeOpen,
  personalOfficerApproved,
  personalOfficerDeclined,
  personalReferred,
  personalWaitingForSlip,
} from '../../test/claimFixtures'
import { ContractViolation } from '../api/parse'
import { canDispute, claimView, claimViews, disputeFor, findClaim, type ClaimView, type ModelContext } from './trackerModel'

const CTX: ModelContext = { slaHours: 24, creditMinutes: 4, now: '2025-08-19T17:05:00+05:30' }
const view = (item: ClaimItem, all: readonly ClaimItem[] = [item], ctx: ModelContext = CTX): ClaimView => claimView(item, all, ctx)
const copy = (key: string, params?: Record<string, string | number>) => ({ kind: 'copy', key, ...(params ? { params } : {}) })
const states = (v: ClaimView) => v.steps.map((s) => [s.id, s.status, s.stateKey, s.icon])

describe('the five steps in each situation', () => {
  it('area, approved, credit pending: Paid is the step that is working, and it says so in words', () => {
    const v = view(areaCreditPending())
    expect(v.pill).toEqual({ word: 'APPROVED', labelKey: 'claim.status.approved_pending', tone: 'decided', icon: 'clock' })
    expect(states(v)).toEqual([
      ['detected', 'completed', 'tracker.state.done', 'done'],
      ['checked', 'completed', 'tracker.state.done', 'done'],
      ['decided', 'completed', 'tracker.state.done', 'done'],
      ['paid', 'current', 'tracker.state.now', 'working'],
      ['edi', 'pending', 'tracker.state.waiting', 'waiting'],
    ])
    expect(v.steps[2].headline).toEqual(copy('TRACK_DECIDED_AUTO', { amount: '₹1,380' }))
    expect(v.steps[3].headline).toEqual(copy('TRACK_PAID_PENDING', { amount: '₹1,380' }))
    expect(v.steps[3].detail).toEqual(copy('TRACK_PAID_ETA', { minutes: 4 }))
    expect(v.steps[3].simulated).toBe('payment')
    expect(v.steps[4].simulated).toBeNull()
    expect(v.nextLine).toEqual(copy('tracker.next.after_decided'))
    expect(v.canDispute).toBe(false)
    expect(v.amountLabel).toBe('₹1,380')
  })

  it('area, paid, lender asked: Paid is done at 17:04 and the lender decides', () => {
    const v = view(areaLenderAsked())
    expect(v.pill).toEqual({ word: 'APPROVED', labelKey: 'claim.status.paid', tone: 'paid', icon: 'check' })
    expect(v.steps[3]).toMatchObject({ status: 'completed', at: '2025-08-19T17:04:00+05:30', headline: null, simulated: 'payment' })
    expect(v.steps[3].detail).toEqual({ kind: 'api', hi: 'आज के सेटलमेंट के साथ जमा', en: "Credited with today's settlement" })
    expect(v.steps[4]).toMatchObject({ status: 'current', stateKey: 'tracker.state.now', icon: 'working', simulated: 'lender' })
    expect(v.steps[4].headline).toEqual(copy('TRACK_EDI_REQUESTED'))
    expect(v.nextLine).toEqual(copy('tracker.next.after_paid'))
    expect(v.canDispute).toBe(true)
  })

  it('area, paid, lender granted: the lender answer is the API line, and every step is done', () => {
    const v = view(areaLenderGranted())
    expect(states(v).map(([, status]) => status)).toEqual(['completed', 'completed', 'completed', 'completed', 'completed'])
    expect(v.steps[4]).toMatchObject({ result: 'GRANTED', headline: null, simulated: 'lender', at: '2025-08-19T17:05:00+05:30' })
    expect(v.steps[4].detail).toEqual({ kind: 'api', hi: 'कल की ₹600 की किस्त रोक दी गई है।', en: "Tomorrow's ₹600 instalment is paused." })
    expect(v.nextLine).toEqual(copy('tracker.next.done'))
  })

  it('area, paid, lender refused: "not available", due as usual, and no reason code anywhere', () => {
    const v = view(areaLenderRefused())
    expect(v.steps[4]).toMatchObject({ status: 'completed', result: 'REFUSED', detail: null, simulated: 'lender' })
    expect(v.steps[4].headline).toEqual(copy('TRACK_EDI_REFUSED'))
    expect(JSON.stringify(v)).not.toContain('IN_ARREARS')
    expect(JSON.stringify(v)).not.toContain('reason_code')
  })

  it('area, paid, lender did not answer: says so and keeps the instalment due', () => {
    const base = areaLenderRefused()
    const silent = { ...base, steps: [...base.steps.slice(0, 4), { ...base.steps[4], result: 'NO_RESPONSE' as const, reason_code: null }] }
    expect(view(silent).steps[4].headline).toEqual(copy('TRACK_EDI_NO_RESPONSE'))
  })

  it('area, paid, no loan: the holiday step is skipped with "No loan on file"', () => {
    const v = view(areaNoLoan())
    expect(v.steps[4]).toMatchObject({ status: 'skipped', stateKey: 'tracker.state.na', icon: 'skipped', simulated: null })
    expect(v.steps[4].headline).toEqual(copy('TRACK_EDI_NONE'))
    expect(v.nextLine).toEqual(copy('tracker.next.done'))
  })

  it('declined: stops at Decided with the reason, and Paid and the holiday are skipped', () => {
    const v = view(areaDeclined())
    expect(v.pill).toEqual({ word: 'DECLINED', labelKey: 'claim.status.declined', tone: 'blocked', icon: 'x' })
    expect(states(v)).toEqual([
      ['detected', 'completed', 'tracker.state.done', 'done'],
      ['checked', 'completed', 'tracker.state.done', 'done'],
      ['decided', 'completed', 'tracker.state.stopped', 'stopped'],
      ['paid', 'skipped', 'tracker.state.na', 'skipped'],
      ['edi', 'skipped', 'tracker.state.na', 'skipped'],
    ])
    expect(v.steps[2].headline).toEqual(copy('claim.status.declined'))
    expect(v.steps[2].detail).toMatchObject({ kind: 'api', en: "The name on the slip doesn't match your KYC, so this claim can't be approved." })
    expect(v.steps.slice(3).map((s) => [s.headline, s.detail, s.simulated])).toEqual([[null, null, null], [null, null, null]])
    expect(v.amountLabel).toBeNull()
    expect(v.canDispute).toBe(false)
    expect(v.nextLine).toEqual(copy('tracker.next.declined'))
  })

  it('personal, waiting for the slip: Detected is current, "Waiting for your slip", and nothing else has happened', () => {
    const v = view(personalWaitingForSlip())
    expect(v.pill).toEqual({ word: 'WAITING_FOR_SLIP', labelKey: 'claim.status.waiting_slip', tone: 'neutral', icon: 'hourglass' })
    expect(states(v)).toEqual([
      ['detected', 'current', 'tracker.state.now', 'working'],
      ['checked', 'pending', 'tracker.state.waiting', 'waiting'],
      ['decided', 'pending', 'tracker.state.waiting', 'waiting'],
      ['paid', 'pending', 'tracker.state.waiting', 'waiting'],
      ['edi', 'pending', 'tracker.state.waiting', 'waiting'],
    ])
    expect(v.steps[0].headline).toEqual(copy('claim.status.waiting_slip'))
    expect(v.amountLabel).toBeNull()
    expect(v.caseChip).toBeNull()
  })

  it('personal, referred: Decided is with a person, with the case chip and the 24 hour clock; Paid and the holiday wait', () => {
    const v = view(personalReferred(), [personalReferred()], { ...CTX, now: '2025-08-21T11:20:00+05:30' })
    expect(v.pill).toEqual({ word: 'REFERRED', labelKey: 'claim.status.referred', tone: 'referred', icon: 'person' })
    expect(states(v)).toEqual([
      ['detected', 'completed', 'tracker.state.done', 'done'],
      ['checked', 'completed', 'tracker.state.done', 'done'],
      ['decided', 'current', 'claim.status.referred', 'person'],
      ['paid', 'pending', 'tracker.state.waiting', 'waiting'],
      ['edi', 'pending', 'tracker.state.waiting', 'waiting'],
    ])
    expect(v.steps[2].headline).toBeNull() // the state word already says "With a claims officer"
    expect(v.caseChip).toEqual({ caseId: 'C-2291' })
    expect(v.clock).toEqual({ kind: 'left', hours: 24 })
    expect(v.amountLabel).toBeNull()
    expect(v.nextLine).toEqual(copy('tracker.next.referred', { sla_hours: 24 }))
    expect(v.canDispute).toBe(false)
  })

  it('personal, officer approved: "Approved by a claims officer" with the amount beside it, and Paid follows', () => {
    const v = view(personalOfficerApproved())
    expect(v.officerApproved).toBe(true)
    expect(v.pill).toEqual({ word: 'APPROVED', labelKey: 'TRACK_DECIDED_OFFICER', tone: 'decided', icon: 'clock' })
    expect(v.steps[2]).toMatchObject({ status: 'completed', amountLabel: '₹1,500' })
    expect(v.steps[2].headline).toEqual(copy('TRACK_DECIDED_OFFICER'))
    expect(v.steps[3]).toMatchObject({ status: 'current', icon: 'working' })
    expect(v.caseChip).toBeNull()
    expect(v.clock).toBeNull()
  })

  it('personal, officer declined: "Not paid" and the officer reason, and Paid and the holiday are skipped', () => {
    const v = view(personalOfficerDeclined())
    expect(v.pill.word).toBe('DECLINED')
    expect(v.steps[2]).toMatchObject({ status: 'completed', stateKey: 'tracker.state.stopped', icon: 'stopped' })
    expect(v.steps[2].headline).toEqual(copy('claim.status.declined'))
    expect(v.steps[2].detail).toMatchObject({ kind: 'api' })
    expect(v.steps.slice(3).map((s) => s.status)).toEqual(['skipped', 'skipped'])
  })
})

describe('a dispute is its own card', () => {
  it('open: a question about the payout, the case, the clock and the unchanged amount, with no steps', () => {
    const v = view(disputeOpen(), [disputeOpen(), claim()], { ...CTX, now: '2025-08-19T17:12:00+05:30' })
    expect(v).toMatchObject({ id: 'C-2291', kind: 'DISPUTE', kindKey: 'tracker.kind.dispute', claimId: null, disputedClaimId: 'CL-000142', amountLabel: '₹1,380', steps: [], resolution: null })
    expect(v.pill).toEqual({ word: 'DISPUTE_OPEN', labelKey: 'claim.status.question_open', tone: 'referred', icon: 'scale' })
    expect(v.caseChip).toEqual({ caseId: 'C-2291' })
    expect(v.clock).toEqual({ kind: 'left', hours: 24 })
    expect(v.nextLine).toEqual(copy('TRACK_DISPUTE_OPEN', { case_id: 'C-2291', sla_hours: 24 }))
  })

  it('closed: the amount stays, the note shows, and there is no clock', () => {
    const v = view(disputeClosed(), [disputeClosed(), claim()])
    expect(v.pill).toEqual({ word: 'DISPUTE_CLOSED', labelKey: 'claim.status.question_closed', tone: 'neutral', icon: 'check' })
    expect(v).toMatchObject({ amountLabel: '₹1,380', resolution: 'Amount confirmed', clock: null })
    expect(v.nextLine).toEqual(copy('TRACK_DISPUTE_CLOSED', { amount: '₹1,380' }))
  })
})

describe('what the model refuses and what it leaves out', () => {
  it('an AREA claim is never REFERRED', () => {
    const wrong = claim({ outcome: 'REFERRED', case_id: 'C-2291', case_status: 'OPEN' })
    expect(() => view(wrong)).toThrow(ContractViolation)
  })

  it('leaves out a line that needs a rule number it does not have, and never invents one', () => {
    const none: ModelContext = { slaHours: null, creditMinutes: null, now: null }
    expect(view(areaCreditPending(), [areaCreditPending()], none).steps[3].detail).toBeNull()
    expect(view(personalReferred(), [personalReferred()], none).nextLine).toBeNull()
    expect(view(disputeOpen(), [disputeOpen()], none).nextLine).toBeNull()
    expect(view(disputeOpen(), [disputeOpen()], none).clock).toEqual({ kind: 'due', at: '2025-08-20T17:12:00+05:30' })
  })

  it('rounds the hours left up, and says overdue once the time has passed while the case is open', () => {
    const open = disputeOpen()
    expect(view(open, [open], { ...CTX, now: '2025-08-20T10:30:00+05:30' }).clock).toEqual({ kind: 'left', hours: 7 })
    expect(view(open, [open], { ...CTX, now: '2025-08-20T17:12:00+05:30' }).clock).toEqual({ kind: 'overdue' })
    expect(view(open, [open], { ...CTX, now: '2025-08-21T09:00:00+05:30' }).clock).toEqual({ kind: 'overdue' })
  })
})

describe('the list', () => {
  it('keeps the API order and names each card by its claim, or by its case for a dispute', () => {
    const items = [disputeOpen(), claim()]
    expect(claimViews(items, CTX).map((v) => [v.id, v.kind])).toEqual([['C-2291', 'DISPUTE'], ['CL-000142', 'AREA']])
  })

  it('finds a claim by its id, and the dispute that is about it', () => {
    const items = [disputeClosed(), disputeOpen(), claim()]
    expect(findClaim(items, 'CL-000142')?.kind).toBe('AREA')
    expect(findClaim(items, 'CL-999999')).toBeNull()
    expect(disputeFor(items, 'CL-000142')?.case_status).toBe('CLOSED')
    expect(disputeFor([claim()], 'CL-000142')).toBeNull()
  })

  it('offers "This is wrong" on a paid claim with no open dispute, and not while one is open', () => {
    const paid = claim()
    expect(canDispute(paid, [paid])).toBe(true)
    expect(canDispute(paid, [disputeOpen(), paid])).toBe(false)
    expect(canDispute(paid, [disputeClosed(), paid])).toBe(true)
    expect(canDispute(areaCreditPending(), [areaCreditPending()])).toBe(false)
    expect(canDispute(areaDeclined(), [areaDeclined()])).toBe(false)
    expect(canDispute(personalReferred(), [personalReferred()])).toBe(false)
    expect(canDispute(disputeOpen(), [disputeOpen()])).toBe(false)
  })
})
