/** The five doctor checks in the officer's case headline, "Why a human" and the evidence (SPEC §9.2, design 2.11, R10). */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Case, CaseEvidence, Check, Decision } from '../../api/types'
import { caseHeadline, FAILURE_CLAUSES } from './caseSummary'
import { Evidence } from './Evidence'
import { FAILURE_TITLES, humanReasons } from './whyHuman'

const CODES = ['HOSPITAL_IDENTIFIED', 'DOCTOR_IDENTIFIED', 'VERIFICATION_CONSENT', 'DOCTOR_NOT_DENIED', 'DOCTOR_CONFIRMED'] as const

const check = (code: string, status: Check['status'], severity: Check['severity'] = 'SOFT', observed: string | null = null): Check => ({ code, status, severity, label_en: `${code} label`, detail_en: '', observed, required: null })

describe('doctor checks for the officer', () => {
  it.each(CODES)('%s has a headline clause and a "Why a human" title', (code) => {
    expect(FAILURE_CLAUSES[code]).toMatch(/\w/)
    expect(FAILURE_TITLES[code]).toMatch(/\w/)
  })

  it('heads a refused-consent case in plain words, with the rule underneath', () => {
    const decision = { id: 'D-000002', outcome: 'REFERRED', amount_label: '₹1,500', checks: [check('VERIFICATION_CONSENT', 'FAIL', 'SOFT', 'declined')] } as unknown as Decision
    const item = { kind: 'PERSONAL_CLAIM_REVIEW', summary_en: 'x', merchant_name: "Anil's Tea Stall", decision, evidence: {} } as unknown as Case
    expect(caseHeadline(item)).toEqual({
      text: "Personal claim ₹1,500 for Anil's Tea Stall sent to a human: the merchant would rather we didn’t ask the doctor.",
      rule: 'Rule VERIFICATION_CONSENT failed · declined',
    })
  })

  it('lists an unanswered doctor among the reasons', () => {
    expect(humanReasons([check('DOCTOR_CONFIRMED', 'UNSURE', 'SOFT', 'not asked')], {})).toEqual([{ code: 'DOCTOR_CONFIRMED', tone: 'amber', title: 'Unsure: DOCTOR_CONFIRMED label', detail: 'not asked' }])
    expect(humanReasons([check('DOCTOR_NOT_DENIED', 'FAIL', 'HARD')], {})[0].title).toBe('The doctor said the patient did not attend')
  })
})

describe('doctor evidence', () => {
  const evidence: CaseEvidence = {
    slip: { media_url: '/slips/anil_admission_slip.png', patient_name: 'Anil R. Jadhav', admission_date: '2025-08-20', discharge_date: null, hospital_name: 'KEM Hospital, Parel', document_type: 'admission_slip', confidence: 0.94, source: 'simulated', doctor_name: 'Dr S. Rao', doctor_registration_no: 'MMC-2011-45817' },
    doctor_verification: { status: 'NO_ANSWER', doctor_name: 'Dr S. Rao', hospital_name: 'KEM Hospital, Parel', requested_at: '2025-08-21T11:22:00+05:30', answered_at: null, via: 'TELEGRAM' },
  }

  it('shows the doctor read from the slip and how the confirmation went', () => {
    render(<Evidence evidence={evidence} />)
    expect(screen.getByText('MMC-2011-45817')).toBeTruthy()
    const block = screen.getByTestId('doctor-verification')
    expect(block.textContent).toContain('No answer')
    expect(block.textContent).toContain('Dr S. Rao · KEM Hospital, Parel')
    expect(block.textContent).toContain('asked 11:22')
    expect(block.textContent).toContain('Telegram (a real doctor chat)')
  })

  it('leaves the doctor out when the server sends no doctor keys', () => {
    const { slip } = evidence
    if (!slip) throw new Error('no slip')
    const { doctor_name: _n, doctor_registration_no: _r, ...plain } = slip
    render(<Evidence evidence={{ slip: plain }} />)
    expect(screen.queryByText('Registration no.')).toBeNull()
    expect(screen.queryByTestId('doctor-verification')).toBeNull()
  })
})
