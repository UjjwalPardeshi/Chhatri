/**
 * The five doctor checks (SPEC §9.2, design 2.11) on the merchant's receipt and on Why: a plain label for each in
 * every language, the TRACK_REFERRED line when the claim went to a person over one, and the REASON line when a HARD
 * one declined it.
 */
import { describe, expect, it } from 'vitest'

import type { Receipt, ReceiptCheck } from '../../api/types'
import { en } from '../copy/en'
import { hi } from '../copy/hi'
import { mr } from '../copy/mr'
import { checkLabelKey } from './ReceiptChecks'
import { reasonKeys } from './WhyReasons'

const CODES = ['HOSPITAL_IDENTIFIED', 'DOCTOR_IDENTIFIED', 'VERIFICATION_CONSENT', 'DOCTOR_NOT_DENIED', 'DOCTOR_CONFIRMED'] as const

const check = (code: string, severity: 'HARD' | 'SOFT', status: ReceiptCheck['status']): ReceiptCheck => ({
  code,
  severity,
  status,
  label_en: code,
  detail_en: code,
  observed: null,
  required: null,
  clause: null,
  erased: false,
  sources: [],
})

const receipt = (outcome: Receipt['decision']['outcome'], checks: ReceiptCheck[]): Receipt => ({ decision: { outcome, decided_by: 'policy-engine' }, checks }) as unknown as Receipt

describe('doctor checks on the receipt', () => {
  it.each(CODES)('%s has a plain label in English, Hindi and Marathi', (code) => {
    const key = checkLabelKey(code)
    expect(key).toBe(`CHK_${code}`)
    if (key === null) throw new Error('no key')
    expect([en[key], hi[key], mr[key]].every((text) => typeof text === 'string' && text.length > 0)).toBe(true)
  })

  it('reads the labels as the merchant would', () => {
    expect(CODES.map((code) => en[checkLabelKey(code) ?? 'CHK_COVER_IN_FORCE'])).toEqual([
      'The hospital is in our list of hospitals',
      "The doctor is on that hospital's list",
      'You agreed that we may ask the doctor',
      'The doctor did not say no',
      'The doctor confirmed your visit',
    ])
  })
})

describe('doctor checks on Why', () => {
  it('says why a person decides: no permission to ask, or the doctor has not answered', () => {
    expect(reasonKeys(receipt('REFERRED', [check('VERIFICATION_CONSENT', 'SOFT', 'FAIL')]))).toEqual(['TRACK_REFERRED_CONSENT'])
    expect(reasonKeys(receipt('REFERRED', [check('DOCTOR_CONFIRMED', 'SOFT', 'UNSURE')]))).toEqual(['TRACK_REFERRED_DOCTOR'])
  })

  it('says why a claim was declined by a HARD doctor check', () => {
    expect(reasonKeys(receipt('DECLINED', [check('HOSPITAL_IDENTIFIED', 'HARD', 'FAIL')]))).toEqual(['REASON_HOSPITAL_IDENTIFIED'])
    expect(reasonKeys(receipt('DECLINED', [check('DOCTOR_IDENTIFIED', 'HARD', 'FAIL')]))).toEqual(['REASON_DOCTOR_IDENTIFIED'])
    expect(reasonKeys(receipt('DECLINED', [check('DOCTOR_NOT_DENIED', 'HARD', 'FAIL')]))).toEqual(['REASON_DOCTOR_NOT_DENIED'])
    expect(en.REASON_DOCTOR_NOT_DENIED).toBe('The hospital told us you were not treated there on that day.')
  })
})
