/** Policy rules in their units (SPEC §9.1 rules, §19 GET /api/policy). */
import { describe, expect, it } from 'vitest'

import { formatRule, humanise, ruleRows } from './ruleFormat'

describe('rule format', () => {
  it('moves the unit from the key into the value', () => {
    expect(formatRule('daily_cap_rupees', 2500)).toEqual({ label: 'Daily cap', value: '₹2,500' })
    expect(formatRule('annual_limit_rupees', 30000)).toEqual({ label: 'Annual limit', value: '₹30,000' })
    expect(formatRule('index_floor_pct', 50)).toEqual({ label: 'Index floor', value: '50%' })
    expect(formatRule('waiting_period_days', 7)).toEqual({ label: 'Waiting period', value: '7 days' })
    expect(formatRule('payout_rail_delay_minutes', 1)).toEqual({ label: 'Payout rail delay', value: '1 minute' })
    expect(formatRule('consecutive_hours', 3)).toEqual({ label: 'Hours in a row', value: '3 hours' })
  })

  it('shows fractions as percentages and leaves other values as they are', () => {
    expect(formatRule('payout_share', 0.5)).toEqual({ label: 'Payout share', value: '50%' })
    expect(formatRule('slip_confidence_min', 0.8)).toEqual({ label: 'Slip confidence min', value: '80%' })
    expect(formatRule('loading', 0.35)).toEqual({ label: 'Loading', value: '0.35' })
    expect(formatRule('version', 'pilot-0.1')).toEqual({ label: 'Version', value: 'pilot-0.1' })
    expect(formatRule('kinds', ['area', 'personal'])).toEqual({ label: 'Kinds', value: 'area, personal' })
    expect(humanise('name_match_min_score')).toBe('Name match min score')
  })

  it('flattens nested sections', () => {
    expect(ruleRows({ version: 'pilot-0.1', area: { daily_cap_rupees: 2500 } })).toEqual([
      ['Version', 'pilot-0.1'],
      ['Area · Daily cap', '₹2,500'],
    ])
  })
})
