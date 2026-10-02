/** Rule numbers reach the words as {placeholders}: nothing numeric is typed into a string (fs-04 6.2, copy deck 1.2). */
import { describe, expect, it } from 'vitest'

import { parseRules } from '../api/rules'
import { POLICY } from '../../mock/fixtures'
import { t } from './copy'
import { ANNUAL_WINDOW_DAYS, rulesParams } from './copyRules'

const rules = parseRules(POLICY)

describe('rulesParams', () => {
  it('names every rule number the deck uses, with money as the labels made from the rules', () => {
    expect(rulesParams(rules)).toEqual({
      share_pct: 50,
      area_cap: '₹2,500',
      personal_cap: '₹1,500',
      annual_limit: '₹30,000',
      window_days: ANNUAL_WINDOW_DAYS,
      waiting_days: 7,
      lookahead_hours: 72,
      floor_pct: 50,
      hours: 3,
      max_auto_days: 3,
      first_days: 30,
      sla_hours: 24,
      minutes: 4,
      rules_version: 'pilot-0.1',
      name_match_min: 85,
    })
  })

  it('counts the yearly limit over 365 days, the backend rolling window', () => {
    expect(ANNUAL_WINDOW_DAYS).toBe(365)
  })

  it('reaches the words: a rules change changes the sentence, in both languages', () => {
    const ten = { ...rules, waiting_period_days: 10 }
    expect(t('explain.c5.body', 'en', rulesParams(rules))).toContain('starts 7 days after you ask')
    expect(t('explain.c5.body', 'en', rulesParams(ten))).toContain('starts 10 days after you ask')
    expect(t('explain.c5.body', 'hi', rulesParams(ten))).toContain('10 दिन बाद')
    expect(t('explain.c4.body', 'en', rulesParams(rules))).toContain('₹2,500 for rain and ₹1,500 for hospital cash')
  })
})
