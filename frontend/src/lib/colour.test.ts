import { describe, expect, it } from 'vitest'

import { COLOUR_STOPS, indexColour, legendGradient, legendRule, NO_DATA_COLOUR, SCALE_AMBER, SCALE_GREEN, SCALE_RED } from './colour'

describe('deck colour scale (SPEC §20): 40% red → 70% amber → 100%+ green', () => {
  it('pins the three named stops', () => {
    expect(indexColour(40)).toBe(SCALE_RED)
    expect(indexColour(70)).toBe(SCALE_AMBER)
    expect(indexColour(100)).toBe(SCALE_GREEN)
    expect(SCALE_RED).toBe('#b91c1c')
    expect(SCALE_AMBER).toBe('#e39a4f')
  })

  it('clamps outside the scale', () => {
    expect(indexColour(0)).toBe(SCALE_RED)
    expect(indexColour(37)).toBe(SCALE_RED)
    expect(indexColour(140)).toBe(SCALE_GREEN)
  })

  it('interpolates between stops', () => {
    const mid = indexColour(47.5)
    expect(mid).toMatch(/^#[0-9a-f]{6}$/)
    expect(mid).not.toBe(SCALE_RED)
    expect(indexColour(55)).toBe(COLOUR_STOPS[1].hex)
  })

  it('uses grey for missing data', () => {
    expect(indexColour(null)).toBe(NO_DATA_COLOUR)
    expect(indexColour(undefined)).toBe(NO_DATA_COLOUR)
    expect(indexColour(Number.NaN)).toBe(NO_DATA_COLOUR)
  })

  it('builds the legend gradient from the same stops', () => {
    expect(legendGradient()).toBe(`linear-gradient(90deg, ${SCALE_RED} 0%, #d6603a 25%, ${SCALE_AMBER} 50%, #e7d38b 75%, ${SCALE_GREEN} 100%)`)
  })

  it('words the legend rule from the published trigger rule, not from a constant', () => {
    expect(legendRule({ floorPct: 50, hours: 3 })).toBe('Pays below 50% for 3 h, with alert')
    expect(legendRule({ floorPct: 45, hours: 4 })).toBe('Pays below 45% for 4 h, with alert')
  })
})
