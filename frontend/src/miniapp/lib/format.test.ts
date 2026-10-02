/** Indian grouping, ASCII digits and dates in the active language (fs-04 section 13, AC-35). */
import { describe, expect, it } from 'vitest'

import { LANGS } from './lang'
import { formatClock, formatDate, formatDateTime, formatNumber } from './format'

const NON_ASCII_DIGIT = /\P{ASCII}/u

describe('formatNumber', () => {
  it('groups digits the Indian way with ASCII digits in every language', () => {
    for (const lang of LANGS) {
      expect(formatNumber(1234567, lang)).toBe('12,34,567')
      expect(formatNumber(4380, lang)).toBe('4,380')
      expect(formatNumber(999, lang)).toBe('999')
      expect(formatNumber(30000, lang)).toBe('30,000')
      expect(NON_ASCII_DIGIT.test(formatNumber(1234567, lang))).toBe(false)
    }
  })

  it('keeps a fraction and a sign', () => {
    expect(formatNumber(18.62, 'mr')).toBe('18.62')
    expect(formatNumber(-1500, 'hi')).toBe('-1,500')
  })
})

describe('formatDate', () => {
  it('date in Hindi, English and Marathi, never moved by the device time zone', () => {
    expect(formatDate('2025-08-25', 'en')).toBe('25 August')
    expect(formatDate('2025-08-25', 'hi')).toBe('25 अगस्त')
    expect(formatDate('2025-08-25', 'mr')).toBe('25 ऑगस्ट')
    expect(formatDate('2025-09-23T17:05:00+05:30', 'en')).toBe('23 September')
  })

  it('uses ASCII digits for Marathi too', () => {
    expect(NON_ASCII_DIGIT.test(formatDate('2025-08-25', 'mr').replace(/[^\d]/g, ''))).toBe(false)
    expect(formatDate('2025-08-25', 'mr')).toContain('25')
  })

  it('shows a dash for a value that is not a date', () => {
    expect(formatDate(null, 'en')).toBe('—')
    expect(formatDate('soon', 'hi')).toBe('—')
  })
})

describe('formatClock and formatDateTime', () => {
  it('reads the wall clock as written in the ISO string', () => {
    expect(formatClock('2025-08-19T17:05:00+05:30')).toBe('17:05')
    expect(formatClock(null)).toBe('—')
  })

  it('joins the date and the time in the active language', () => {
    expect(formatDateTime('2025-08-19T17:05:00+05:30', 'en')).toBe('19 August, 17:05')
    expect(formatDateTime('2025-08-19T17:05:00+05:30', 'hi')).toBe('19 अगस्त, 17:05')
  })
})
