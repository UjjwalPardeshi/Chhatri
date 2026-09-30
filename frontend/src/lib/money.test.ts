import { describe, expect, it } from 'vitest'

import { formatInr, indianGrouping } from './money'
import vectors from './money.vectors.json'

describe('formatInr (SPEC §4.2) matches chhatri.money.format_inr', () => {
  it.each(vectors.vectors)('$paise paise → $label', ({ paise, label }) => {
    expect(formatInr(paise)).toBe(label)
  })

  it('covers the deck numbers', () => {
    expect(formatInr(138_000)).toBe('₹1,380')
    expect(formatInr(15_890_000)).toBe('₹1,58,900')
    expect(formatInr(180)).toBe('₹1.80')
    expect(formatInr(-5_000)).toBe('-₹50')
  })

  it('rejects non-integer paise', () => {
    expect(() => formatInr(1.5)).toThrow(TypeError)
    expect(() => formatInr(Number.NaN)).toThrow(TypeError)
  })
})

describe('indianGrouping', () => {
  it('groups lakhs and crores', () => {
    expect(indianGrouping(0)).toBe('0')
    expect(indianGrouping(999)).toBe('999')
    expect(indianGrouping(1_000)).toBe('1,000')
    expect(indianGrouping(1_234_567)).toBe('12,34,567')
    expect(indianGrouping(100_000_000)).toBe('10,00,00,000')
  })

  it('rejects negatives and fractions', () => {
    expect(() => indianGrouping(-1)).toThrow(RangeError)
    expect(() => indianGrouping(2.5)).toThrow(RangeError)
  })
})
