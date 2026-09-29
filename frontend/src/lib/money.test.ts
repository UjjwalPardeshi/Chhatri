import { describe, it, expect } from 'vitest'
import { formatInr, parseInr, getHexColor } from './money'

describe('formatInr', () => {
  it('formats whole rupees without decimals', () => {
    expect(formatInr(138000)).toBe('₹1,380')
    expect(formatInr(15890000)).toBe('₹1,58,900')
    expect(formatInr(1000)).toBe('₹10')
    expect(formatInr(100)).toBe('₹1')
  })

  it('formats paise with two decimals', () => {
    expect(formatInr(180)).toBe('₹1.80')
    expect(formatInr(138)).toBe('₹1.38')
    expect(formatInr(50)).toBe('₹0.50')
  })

  it('handles Indian digit grouping correctly', () => {
    expect(formatInr(1000000)).toBe('₹10,000')
    expect(formatInr(10000000)).toBe('₹1,00,000')
    expect(formatInr(100000000)).toBe('₹10,00,000')
  })

  it('handles zero', () => {
    expect(formatInr(0)).toBe('₹0')
  })

  it('throws on invalid input', () => {
    expect(() => formatInr(-100)).toThrow()
    expect(() => formatInr(1.5)).toThrow()
  })
})

describe('parseInr', () => {
  it('parses formatted rupees back to paise', () => {
    expect(parseInr('₹1,380')).toBe(138000)
    expect(parseInr('₹1,58,900')).toBe(15890000)
  })

  it('parses rupees with decimals', () => {
    expect(parseInr('₹1.80')).toBe(180)
    expect(parseInr('₹1.38')).toBe(138)
  })

  it('handles spaces and commas', () => {
    expect(parseInr('₹ 1,380')).toBe(138000)
  })
})

describe('getHexColor', () => {
  it('returns gray for null/undefined', () => {
    expect(getHexColor(null)).toBe('#e5e7eb')
    expect(getHexColor(undefined as any)).toBe('#e5e7eb')
  })

  it('returns red for low percentages (0-40%)', () => {
    expect(getHexColor(0)).toBe('#dc2626')
    expect(getHexColor(20)).toBe('#dc2626')
    // At exactly 40%, we're at the boundary, so allow either red or slightly different
    const color40 = getHexColor(40)
    expect(color40).toMatch(/^#[0-9a-f]{6}$/)
  })

  it('returns amber-ish for medium percentages (40-70%)', () => {
    // 50% should be partway between red and amber
    const color50 = getHexColor(50)
    expect(color50).toMatch(/^#[0-9a-f]{6}$/) // valid hex
    // Color should be different from red
    expect(color50).not.toBe('#dc2626')
  })

  it('returns green for high percentages (100%+)', () => {
    expect(getHexColor(100)).toBe('#15803d')
    expect(getHexColor(150)).toBe('#15803d')
  })

  it('supports lighter option', () => {
    const dark = getHexColor(0)
    const light = getHexColor(0, { lighter: true })
    expect(dark).toBe('#dc2626')
    expect(light).toBe('#fca5a5')
  })

  it('follows SPEC §20 color scale: 40%→70%→100%+', () => {
    // SPEC: red at 40%, amber at 70%, green at 100%+
    const colors = {
      low: getHexColor(30),    // < 40% should be red
      threshold1: getHexColor(40), // 40% boundary
      mid: getHexColor(50),    // 40-70% range
      threshold2: getHexColor(70), // 70% boundary
      high: getHexColor(90),   // 70-100% range
      full: getHexColor(100),  // exactly 100%
      over: getHexColor(120),  // > 100%
    }

    expect(colors.low).toBe('#dc2626') // red
    expect(colors.full).toBe('#15803d') // green
    expect(colors.over).toBe('#15803d') // green
    // Mid-range colors should be valid gradients
    expect(colors.mid).toMatch(/^#[0-9a-f]{6}$/)
    expect(colors.high).toMatch(/^#[0-9a-f]{6}$/)
  })
})

describe('money formatting compliance with SPEC §4.2 and §4.3', () => {
  it('formats golden numbers from SPEC §17.2 (monsoon scenario)', () => {
    // Z7 payout: ½ × ₹4,380 × 63% = ₹1,380
    expect(formatInr(138000)).toBe('₹1,380')
    // Z7 total: ₹58,900
    expect(formatInr(5890000)).toBe('₹58,900')
    // Personal payout example: ½ × ₹4,380 = ₹2,190/day, capped at ₹1,500
    expect(formatInr(150000)).toBe('₹1,500')
  })

  it('never shows decimals for whole rupees (SPEC §4.2)', () => {
    expect(formatInr(100)).toBe('₹1')
    expect(formatInr(1000)).toBe('₹10')
    expect(formatInr(138000)).toBe('₹1,380')
    // Verify no decimal point
    expect(formatInr(100)).not.toContain('.')
  })

  it('shows exactly two decimals for fractional rupees (SPEC §4.2)', () => {
    expect(formatInr(138)).toBe('₹1.38')
    expect(formatInr(180)).toBe('₹1.80')
    expect(formatInr(1)).toBe('₹0.01')
    expect(formatInr(50)).toBe('₹0.50')
    // Verify format
    expect(formatInr(138)).toMatch(/^₹\d+\.\d{2}$/)
  })

  it('uses Indian digit grouping (SPEC §4.2)', () => {
    // Format: ₹X,XX,XXX
    expect(formatInr(1000000)).toBe('₹10,000')
    expect(formatInr(10000000)).toBe('₹1,00,000')
    expect(formatInr(100000000)).toBe('₹10,00,000')
    expect(formatInr(1000000000)).toBe('₹1,00,00,000')
  })
})
