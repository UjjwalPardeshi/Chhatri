/** The wording rules of the ladder as pure functions (fs-06 7.2, 7.3 and 8.3): clocks only where a source exists, the portal is never late, the button follows the answer. */
import { describe, expect, it } from 'vitest'

import type { Grievance, LadderStep } from '../api/rights'
import { tr } from '../copy/rights'
import { activeLine, clockLine, escalation, ownPhase, portalDay, timeLeft } from './grievanceModel'
import { lineText } from './rightsKit'

const own = (state: string | null, dueBy = '2025-08-20T17:12:00+05:30'): LadderStep => ({ level: 1, id: 'PAYTM_DISPUTE', name: 'Our claims officer', state: 'ACTIVE', delivery: 'IN_CHHATRI', entered_at: '2025-08-19T17:12:00+05:30', clock: { kind: 'OWN_SLA', hours: 24, due_by: dueBy, state } })
const portal = (startedAt: string | null): LadderStep => ({ level: 3, id: 'BIMA_BHAROSA', name: 'x', state: 'ACTIVE', delivery: 'SELF_REPORTED', entered_at: startedAt, clock: { kind: 'PORTAL_STATED', days: 14, started_at: startedAt, statement_en: 's', state: null } })
const confirm = (id: LadderStep['id']): LadderStep => ({ level: 2, id, name: 'x', state: 'ACTIVE', delivery: 'SIMULATED', entered_at: null, clock: { kind: 'TO_CONFIRM', note_en: 'n' } })

const NOW = '2025-08-19T18:00:00+05:30'

describe('our own clock', () => {
  it('is running before the due time, overdue after it, and answered once the case is closed', () => {
    expect(ownPhase(own('RUNNING'), NOW)).toBe('running')
    expect(ownPhase(own('RUNNING'), '2025-08-20T18:00:00+05:30')).toBe('overdue')
    expect(ownPhase(own('OVERDUE'), NOW)).toBe('overdue')
    expect(ownPhase(own('STOPPED'), '2025-08-21T00:00:00+05:30')).toBe('answered')
  })

  it('counts the time left in hours, then minutes, and never goes negative', () => {
    expect(lineText(timeLeft('2025-08-20T17:12:00+05:30', NOW), 'en')).toBe('24 hours')
    expect(lineText(timeLeft('2025-08-19T18:40:00+05:30', NOW), 'en')).toBe('40 minutes')
    expect(lineText(timeLeft('2025-08-19T17:00:00+05:30', NOW), 'hi')).toBe('1 मिनट')
    expect(lineText(timeLeft('2025-08-19T18:50:00+05:30', NOW), 'en')).toBe('50 minutes')
    expect(lineText(timeLeft('2025-08-19T18:00:30+05:30', NOW), 'en')).toBe('1 minute')
    expect(lineText(timeLeft('2025-08-19T19:00:00+05:30', NOW), 'en')).toBe('1 hour')
  })

  it('writes no time left until the replay clock is known', () => {
    expect(activeLine(own('RUNNING'), null, null)).toBeNull()
  })

  it('writes the sentence of each phase from the deck', () => {
    expect(lineText(activeLine(own('RUNNING'), NOW, null) ?? { key: 'grv.new', params: {} }, 'en')).toBe('Our claims officer is looking at this. Answer due in 24 hours.')
    expect(lineText(activeLine(own('STOPPED'), NOW, null) ?? { key: 'grv.new', params: {} }, 'en')).toBe('Answered: the decision stands. You can read the numbers again in your receipt.')
    expect(lineText(activeLine(own('OVERDUE'), NOW, null) ?? { key: 'grv.new', params: {} }, 'en')).toBe('This is past our 24-hour answer time.')
  })
})

describe('the portal clock', () => {
  it('counts day n of 14 from the filing date and says the days have passed, never that the portal is late', () => {
    expect(portalDay(portal('2025-08-19T00:00:00+05:30'), NOW)).toEqual({ n: 1, days: 14, past: false })
    expect(portalDay(portal('2025-08-10T00:00:00+05:30'), NOW)).toEqual({ n: 10, days: 14, past: false })
    const late = portalDay(portal('2025-08-04T00:00:00+05:30'), NOW)
    expect(late).toMatchObject({ past: true })
    const sentence = lineText(activeLine(portal('2025-08-04T00:00:00+05:30'), NOW, '4 August') ?? { key: 'grv.new', params: {} }, 'en')
    expect(sentence).toBe("The portal's stated 14 days have passed.")
    expect(sentence.toLowerCase()).not.toContain('late')
  })

  it('has no day before the merchant gives a filing date', () => {
    expect(portalDay(portal(null), NOW)).toBeNull()
    expect(lineText(clockLine(portal(null)), 'en')).toBe('The portal says complaints are attended within 14 days.')
  })
})

describe('clocks without a source', () => {
  it('say "to be confirmed" and show no number', () => {
    for (const id of ['INSURER_GRO', 'OMBUDSMAN', 'LENDER_GRIEVANCE', 'PAYTM_SUPPORT'] as const) {
      const text = lineText(clockLine(confirm(id)), 'en')
      expect(text).toContain('to be confirmed')
      expect(text).not.toMatch(/\d/)
    }
  })
})

const grievance = (step: LadderStep, status: Grievance['status'] = 'OPEN', next: Grievance['next_action'] = { id: 'ESCALATE_TO_INSURER_GRO', label_en: 'x' }): Grievance => ({
  grievance_id: 'GR-000001',
  kind: 'DISPUTE',
  topic: 'PAYOUT_AMOUNT',
  respondent: 'INSURER',
  decision_id: 'D-000142',
  case_id: 'C-2291',
  status,
  opened_at: NOW,
  current_step: step.id,
  ladder_steps: [step],
  next_action: next,
})

describe('the escalate button', () => {
  it('waits for the answer or the late hour on the first step, then appears', () => {
    expect(escalation(grievance(own('RUNNING')), NOW)).toBeNull()
    expect(escalation(grievance(own('STOPPED')), NOW)).toMatchObject({ key: 'grv.btn.to_gro', filing: false, from: 'PAYTM_DISPUTE' })
    expect(escalation(grievance(own('RUNNING')), '2025-08-21T00:00:00+05:30')).not.toBeNull()
  })

  it('is on every later step, files with a date for the portal and the Ombudsman, and is absent when solved or last', () => {
    const gro = { ...confirm('INSURER_GRO') }
    expect(escalation(grievance(gro, 'OPEN', { id: 'ESCALATE_TO_BIMA_BHAROSA', label_en: 'x' }), NOW)).toMatchObject({ key: 'grv.btn.to_bharosa', filing: true })
    expect(escalation(grievance(portal('2025-08-19'), 'OPEN', { id: 'ESCALATE_TO_OMBUDSMAN', label_en: 'x' }), NOW)).toMatchObject({ key: 'grv.btn.to_ombudsman', filing: true })
    expect(escalation(grievance(own('STOPPED'), 'RESOLVED'), NOW)).toBeNull()
    expect(escalation(grievance(confirm('OMBUDSMAN'), 'OPEN', null), NOW)).toBeNull()
  })

  it('has Hindi for every button', () => {
    expect(tr('grv.btn.to_gro', 'hi')).toContain('शिकायत अधिकारी')
  })
})
