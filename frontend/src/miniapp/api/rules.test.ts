/** parseRules: the rule numbers of GET /api/policy, strictly read, so no number is typed into copy (card 3.8). */
import { describe, expect, it } from 'vitest'

import { POLICY } from '../../mock/fixtures'
import { ContractViolation } from './parse'
import { parseRules } from './rules'

const violation = (fn: () => unknown): ContractViolation => {
  try {
    fn()
  } catch (error) {
    if (error instanceof ContractViolation) return error
    throw error
  }
  throw new Error('expected a contract violation')
}

describe('parseRules', () => {
  it('reads the numbers the screens need, with money labels made from paise', () => {
    expect(parseRules(POLICY)).toEqual({
      version: 'pilot-0.1',
      payout_share_pct: 50,
      waiting_period_days: 7,
      alert_lookahead_hours: 72,
      annual_limit_paise: 3_000_000,
      annual_limit_label: '₹30,000',
      area_cap_paise: 250_000,
      area_cap_label: '₹2,500',
      personal_cap_paise: 150_000,
      personal_cap_label: '₹1,500',
      index_floor_pct: 50,
      consecutive_hours: 3,
      max_auto_days: 3,
      name_match_min_score: 85,
      dispute_sla_hours: 24,
      payout_rail_delay_minutes: 4,
      first_payment_days: 30,
    })
  })

  it('ignores keys it does not read, since the policy grows', () => {
    expect(parseRules({ ...POLICY, rules: { ...POLICY.rules, brand_new_rule: 1 } }).waiting_period_days).toBe(7)
  })

  it('names the missing or wrong field instead of guessing a number', () => {
    expect(violation(() => parseRules(null)).message).toContain('policy')
    expect(violation(() => parseRules({ rules: null })).message).toContain('policy.rules')
    const rules = POLICY.rules
    expect(violation(() => parseRules({ rules: { ...rules, cover: { alert_lookahead_hours: 72 } } })).message).toContain('policy.rules.cover.waiting_period_days')
    expect(violation(() => parseRules({ rules: { ...rules, annual_limit_rupees: '30000' } })).message).toContain('annual_limit_rupees')
    expect(violation(() => parseRules({ rules: { ...rules, personal: { ...(rules.personal as object), name_match_min_score: 'high' } } })).message).toContain('policy.rules.personal.name_match_min_score')
    expect(violation(() => parseRules({ rules: { ...rules, dispute_sla_hours: 1.5 } })).message).toContain('dispute_sla_hours')
    expect(violation(() => parseRules({ rules: { ...rules, payout_share: 2 } })).message).toContain('payout_share')
    expect(violation(() => parseRules({ rules: { ...rules, version: '' } })).message).toContain('version')
  })
})
