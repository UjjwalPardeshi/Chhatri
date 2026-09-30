/** Case headline, name check and hourly chart helpers (SPEC §9.2, §9.4, §12 evidence). */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Case, CaseEvidence, Check, Decision } from '../../api/types'
import { caseHeadline, FAILURE_CLAUSES } from './caseSummary'
import { gridLines, lowRun, shortRunLabel, totalsLabel } from './HourlyChart'
import { cropStyle, NameCompare, SLIP_NAME_CROP } from './NameCompare'

function check(code: string, status: Check['status'], observed: string | null = null): Check {
  return { code, status, severity: 'SOFT', label_en: `${code} label`, detail_en: '', observed, required: null }
}

const DECISION = { id: 'D-000001', outcome: 'REFERRED', amount_label: '₹1,500', checks: [check('COVER_IN_FORCE', 'PASS'), check('NAME_MATCHES_KYC', 'FAIL', '"Sunil Pawar" · score 41')] } as Decision
const EVIDENCE: CaseEvidence = {
  slip: { media_url: '/slips/mismatch_admission_slip.png', patient_name: 'Sunil Pawar', admission_date: null, discharge_date: null, hospital_name: 'KEM Hospital, Parel', document_type: 'admission_slip', confidence: 0.93, source: 'simulated' },
  kyc_name: 'ANIL RAMESH JADHAV',
  name_score: 41,
}
const CASE = { kind: 'PERSONAL_CLAIM_REVIEW', summary_en: 'Personal claim ₹1,500 referred: NAME_MATCHES_KYC', merchant_name: 'Anil’s Tea Stall', decision: DECISION, evidence: EVIDENCE } as Case
const hour = (h: number, expected: number, actual: number) => ({ hour: `2025-08-20T${String(h).padStart(2, '0')}:00:00+05:30`, expected_paise: expected, actual_paise: actual })

describe('case headline', () => {
  it('says in plain words why a personal claim went to a human, with the rule under it', () => {
    expect(caseHeadline(CASE)).toEqual({
      text: `Personal claim ₹1,500 for Anil’s Tea Stall sent to a human: ${FAILURE_CLAUSES.NAME_MATCHES_KYC}.`,
      rule: 'Rule NAME_MATCHES_KYC failed · score 41 of 85 needed',
    })
  })

  it('explains an officer-approved claim from the referral it superseded, never from a waived pass (SPEC §9.4)', () => {
    const officer = {
      ...DECISION,
      id: 'D-000002',
      outcome: 'APPROVED',
      decided_by: 'officer:officer',
      supersedes: 'D-000001',
      checks: [check('SLIP_READABLE', 'WAIVED_BY_OFFICER', 'admission_slip, confidence 0.94'), check('NAME_MATCHES_KYC', 'WAIVED_BY_OFFICER', 'Sunil Pawar (score 41)')],
    } as Decision
    const approved = { ...CASE, decision: officer }
    expect(caseHeadline(approved, DECISION)).toEqual({
      text: `Personal claim ₹1,500 for Anil’s Tea Stall sent to a human: ${FAILURE_CLAUSES.NAME_MATCHES_KYC}.`,
      rule: 'Rule NAME_MATCHES_KYC failed · score 41 of 85 needed · waived by the officer',
    })
    expect(caseHeadline(approved)).toEqual({ text: CASE.summary_en, rule: null })
  })

  it('names an unsure check and falls back to the server summary otherwise', () => {
    const unsure = { ...CASE, decision: { ...DECISION, checks: [check('DATES_MATCH', 'UNSURE', 'admitted 2025-08-21')] } }
    expect(caseHeadline(unsure).rule).toBe('Rule DATES_MATCH was unsure · admitted 2025-08-21')
    expect(caseHeadline({ ...CASE, kind: 'DISPUTE' })).toEqual({ text: CASE.summary_en, rule: null })
    expect(caseHeadline({ ...CASE, decision: null })).toEqual({ text: CASE.summary_en, rule: null })
    const unknown = { ...CASE, decision: { ...DECISION, checks: [check('NEW_RULE', 'FAIL')] } }
    expect(caseHeadline(unknown).text).toContain('the check “NEW_RULE label” did not pass')
  })
})

describe('name check', () => {
  it('crops the slip to its name line and opens the whole slip', () => {
    expect(cropStyle(SLIP_NAME_CROP).width).toMatch(/%$/)
    render(<NameCompare evidence={EVIDENCE} />)
    expect(screen.getByText('Sunil Pawar')).toBeTruthy()
    expect(screen.getByText('ANIL RAMESH JADHAV')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Compare names/ }))
    expect(screen.getByRole('dialog', { name: 'Hospital slip' })).toBeTruthy()
  })

  it('draws nothing without both names', () => {
    const { container } = render(<NameCompare evidence={{ ...EVIDENCE, kyc_name: undefined }} />)
    expect(container.textContent).toBe('')
  })
})

describe('hourly chart', () => {
  it('draws two or more gridlines when a step fits twice', () => {
    expect(gridLines(45_000)).toEqual([20_000, 40_000])
    expect(gridLines(38_000)).toEqual([10_000, 20_000, 30_000])
    expect(gridLines(15_000)).toEqual([10_000])
    expect(gridLines(5_000)).toEqual([])
  })

  it('shortens the band tag and labels the totals window', () => {
    const silent = lowRun([hour(9, 100, 0), hour(10, 100, 0)])
    const low = lowRun([hour(9, 100, 10)])
    expect(silent && shortRunLabel(silent)).toBe('₹0')
    expect(low && shortRunLabel(low)).toBe('<50%')
    expect(totalsLabel([hour(6, 1, 0), hour(21, 1, 0)])).toBe('06:00–22:00 totals')
    expect(totalsLabel([])).toBe('totals')
  })
})
