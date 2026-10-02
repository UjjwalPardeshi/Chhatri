/** Claims page parts (SPEC §9.2 checks, §9.4 "Why a human", §12 evidence, §20 "Claims"). */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Case, Check, CaseEvidence } from '../../api/types'
import { ZoneTable } from '../backtest/ZoneTable'
import { winner, METRICS } from '../backtest/CompareTable'
import { actorLabel, creditNote, resolutionText } from './CaseDetail'
import { gridStep, lowRun } from './HourlyChart'
import { isStaleRequest, pickCase, queueOrder, runKey, type RunCases } from './selection'
import { humanReasons, sortChecks } from './whyHuman'

function check(code: string, status: Check['status'], severity: Check['severity'] = 'SOFT'): Check {
  return { code, status, severity, label_en: `${code} label`, detail_en: `${code} detail`, observed: `${code} seen`, required: `${code} needed` }
}

const EVIDENCE: CaseEvidence = { slip: { patient_name: 'Sunil Pawar' } as CaseEvidence['slip'], kyc_name: 'ANIL RAMESH JADHAV', name_score: 41 }

const hour = (h: number, expected: number, actual: number) => ({ hour: `2025-08-20T${String(h).padStart(2, '0')}:00:00+05:30`, expected_paise: expected, actual_paise: actual })
const at = (id: string, status: Case['status'], opened: string) => ({ id, status, opened_at: `2025-08-19T${opened}:00+05:30` }) as Case
const zone = (zone_id: string, loss_ratio: number) => ({ zone_id, loss_ratio, premium_per_day_label: '₹3', premiums_paise: 100_00, payouts_paise: Math.round(loss_ratio * 100_00), chhatri_fp: 0, chhatri_fn: 0 })

describe('why a human', () => {
  it('sorts failures first, hard before soft, and words them plainly', () => {
    const checks = [check('COVER_IN_FORCE', 'PASS', 'HARD'), check('DATES_MATCH', 'UNSURE'), check('NAME_MATCHES_KYC', 'FAIL'), check('SLIP_READABLE', 'FAIL', 'HARD')]
    expect(sortChecks(checks).map((c) => c.code)).toEqual(['SLIP_READABLE', 'NAME_MATCHES_KYC', 'DATES_MATCH', 'COVER_IN_FORCE'])
    expect(humanReasons(checks, EVIDENCE)).toEqual([
      { code: 'SLIP_READABLE', tone: 'red', title: 'The slip can’t be read clearly', detail: 'SLIP_READABLE seen · needs SLIP_READABLE needed' },
      { code: 'NAME_MATCHES_KYC', tone: 'red', title: 'Name on the slip doesn’t match KYC', detail: 'Slip: Sunil Pawar · KYC: ANIL RAMESH JADHAV · score 41/100, needs 85' },
      { code: 'DATES_MATCH', tone: 'amber', title: 'Unsure: DATES_MATCH label', detail: 'DATES_MATCH seen · needs DATES_MATCH needed' },
    ])
  })
})

describe('hourly chart', () => {
  it('finds the longest low run and says when it had no payments at all', () => {
    expect(lowRun([hour(9, 100, 90), hour(10, 100, 0), hour(11, 100, 0), hour(12, 100, 80)])).toEqual({ from: 1, to: 2, label: 'No payments' })
    expect(lowRun([hour(9, 100, 40), hour(10, 100, 90), hour(11, 100, 10), hour(12, 100, 20), hour(13, 100, 0)])).toEqual({ from: 2, to: 4, label: 'Below 50% of expected' })
    expect(lowRun([hour(9, 100, 100)])).toBeNull()
  })

  it('reads the policy floor instead of 50', () => {
    const rows = [hour(9, 100, 55), hour(10, 100, 58), hour(11, 100, 90)]
    expect(lowRun(rows)).toBeNull()
    expect(lowRun(rows, 60)).toEqual({ from: 0, to: 1, label: 'Below 60% of expected' })
  })

  it('picks a round gridline under the tallest bar', () => {
    expect(gridStep(48_000)).toBe(20_000)
    expect(gridStep(100_000)).toBe(100_000)
    expect(gridStep(5_000)).toBeNull()
  })
})

describe('case selection', () => {
  const run = runKey({ scenario: 'monsoon', start: '2025-08-19T08:00:00+05:30' })
  const all: RunCases = { run: run ?? '', filter: 'ALL', cases: [at('C-1', 'OPEN', '10:00'), at('C-2', 'APPROVED', '11:00')] }

  it('keeps a requested case from this run and falls back to the first one', () => {
    expect(run).toBe('monsoon|2025-08-19T08:00:00+05:30')
    expect(runKey(null)).toBeNull()
    expect(pickCase('C-2', all, run)).toBe('C-2')
    expect(pickCase(null, all, run)).toBe('C-1')
    expect(pickCase('C-9', all, run)).toBe('C-1')
    expect(isStaleRequest('C-9', all, run)).toBe(true)
    expect(isStaleRequest('C-2', all, run)).toBe(false)
  })

  it('never picks from a queue loaded for another run, and trusts a filtered queue', () => {
    expect(pickCase('C-2', all, 'illness|x')).toBeNull()
    expect(isStaleRequest('C-2', all, 'illness|x')).toBe(false)
    const open: RunCases = { ...all, filter: 'OPEN', cases: [all.cases[0]] }
    expect(pickCase('C-2', open, run)).toBe('C-2')
  })

  it('lists open cases first, newest first within each group', () => {
    const cases = [at('A', 'APPROVED', '12:00'), at('B', 'OPEN', '09:00'), at('C', 'OPEN', '11:00'), at('D', 'DECLINED', '13:00')]
    expect(queueOrder(cases).map((c) => c.id)).toEqual(['C', 'B', 'D', 'A'])
  })

  it('says when an approved amount reaches the merchant on the replay clock (SPEC §10 credited_at)', () => {
    const approved = { merchant_name: 'Anil’s Tea Stall', decision: { amount_label: '₹1,500', outcome: 'APPROVED', decided_at: '2025-08-21T11:25:00+05:30' } } as Case
    expect(creditNote(approved, 4, '2025-08-21T11:25:00+05:30')).toBe('₹1,500 reaches Anil’s Tea Stall at 11:29 on the replay clock, with the settlement.')
    expect(creditNote(approved, 4, '2025-08-21T11:30:00+05:30')).toBe('₹1,500 credited to Anil’s Tea Stall at 11:29, with the settlement.')
    expect(creditNote(approved, null, '2025-08-21T11:30:00+05:30')).toBe('₹1,500 reaches Anil’s Tea Stall with the next settlement.')
    expect(creditNote({ ...approved, decision: { ...approved.decision, outcome: 'DECLINED' } } as Case, 4, '')).toBeNull()
  })

  it('names actors and resolutions in plain words (SPEC §11 actors)', () => {
    expect(actorLabel('officer:officer')).toBe('claims officer')
    expect(actorLabel('officer:rk')).toBe('claims officer rk')
    expect(actorLabel('policy-engine')).toBe('policy engine')
    expect(actorLabel('workflow:payout')).toBe('workflow:payout')
    const resolved = { status: 'APPROVED', resolution: 'Approved by officer:officer', resolved_by: 'officer:officer' } as Case
    expect(resolutionText(resolved)).toBe('Approved by claims officer')
    expect(resolutionText({ ...resolved, resolution: 'Slip checked by phone' })).toBe('“Slip checked by phone” · claims officer')
    expect(resolutionText({ ...resolved, resolution: null, resolved_by: null })).toBe('Approved')
    expect(resolutionText({ status: 'CLOSED', resolution: 'Payout confirmed by a claims officer', resolved_by: 'officer:officer' })).toBe('Payout confirmed by a claims officer')
  })
})

describe('backtest tables', () => {
  it('marks the better trigger only where better has a direction', () => {
    const base = { name: 'chhatri', recall: 0.91, false_positive_rate: 0.05 } as const
    const triggers = [base, { ...base, name: 'weather_only', recall: 0.55, false_positive_rate: 0.56 }] as unknown as Parameters<typeof winner>[1]
    expect(METRICS.map((m) => winner(m, triggers))).toEqual(['chhatri', 'chhatri', null, null, null])
  })

  it('draws the priced-for line and flags zones above it', () => {
    const { container } = render(<ZoneTable zones={[zone('Z3', 0.62), zone('Z7', 0.68)]} target={0.65} />)
    expect(container.querySelectorAll('.ratio__target')).toHaveLength(2)
    expect(container.querySelectorAll('.ratio--over')).toHaveLength(1)
    expect(container.querySelector('.ratio--over')?.getAttribute('title')).toBe('Z7: payouts ₹68 of premiums ₹100 = 68% · priced for 65%')
    expect(screen.getByText(/Premiums are priced for a 65% loss ratio\. Amber bars paid out more than that\./)).toBeTruthy()
  })
})
