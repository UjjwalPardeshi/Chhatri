import { describe, expect, it } from 'vitest'

import { POLICY } from '../mock/fixtures'
import { railDelayMinutes, ruleNumber, targetLossRatio } from './rules'

describe('rules', () => {
  it('reads nested numbers by dotted path', () => {
    expect(ruleNumber(POLICY.rules, 'premium.loading')).toBe(0.35)
    expect(ruleNumber(POLICY.rules, 'area.index_floor_pct')).toBe(50)
  })

  it('returns null for missing, non-numeric or absent rules', () => {
    expect(ruleNumber(POLICY.rules, 'premium.nope')).toBeNull()
    expect(ruleNumber(POLICY.rules, 'version')).toBeNull()
    expect(ruleNumber(null, 'premium.loading')).toBeNull()
    expect(ruleNumber({ a: 1 }, 'a.b')).toBeNull()
  })

  it('derives the rail delay and the pricing target loss ratio', () => {
    expect(railDelayMinutes(POLICY.rules)).toBe(4)
    expect(targetLossRatio(POLICY.rules)).toBeCloseTo(0.65)
    expect(targetLossRatio({ premium: { loading: 1.2 } })).toBeNull()
    expect(targetLossRatio(undefined)).toBeNull()
  })
})
