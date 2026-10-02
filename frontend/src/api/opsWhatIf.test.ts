/** The strict parsers of GET /api/ops/summary and POST /api/whatif/area. */
import { describe, expect, it } from 'vitest'

import { parseOpsSummary, parseWhatIf } from './opsWhatIf'

const OPS = {
  as_of: '2025-08-19T17:06:00+05:30',
  day: '2025-08-19',
  open_cases: 1,
  cases_by_kind: { PERSONAL_CLAIM_REVIEW: 0, DISPUTE: 1, AREA_REVIEW: 0 },
  overdue_cases: 0,
  next_due_case: { id: 'C-2291', kind: 'DISPUTE', merchant_id: 'S-0142', opened_at: '2025-08-19T17:06:00+05:30', due_by: '2025-08-20T17:06:00+05:30', due_in_minutes: 1440 },
  claims_today: { automatic: 312, human: 0, waiting: 0, automatic_share_pct: 100 },
  payouts_today: {
    credited_count: 312,
    credited_paise: 42_542_000,
    credited_label: '₹4,25,420',
    pending_count: 0,
    failed_count: 0,
    by_zone: {
      Z3: { count: 141, paise: 20_671_900, label: '₹2,06,719' },
      Z7: { count: 46, paise: 5_890_000, label: '₹58,900' },
      Z12: { count: 125, paise: 15_980_100, label: '₹1,59,801' },
    },
  },
  holiday_requests_today: { GRANTED: 123, REFUSED: 0, NO_RESPONSE: 0, REQUESTED: 0 },
}

const VIOLATION = expect.objectContaining({ code: 'contract_violation' })

describe('parseOpsSummary', () => {
  it('accepts the example of data-model 5.7', () => {
    expect(parseOpsSummary(OPS)).toEqual(OPS)
  })

  it('accepts nothing open, no claims and no X4', () => {
    const none = { ...OPS, open_cases: 0, cases_by_kind: { PERSONAL_CLAIM_REVIEW: 0, DISPUTE: 0, AREA_REVIEW: 0 }, next_due_case: null, claims_today: { automatic: 0, human: 0, waiting: 0, automatic_share_pct: null }, holiday_requests_today: null }
    expect(parseOpsSummary(none).next_due_case).toBeNull()
  })

  it('refuses a body the strip could not trust', () => {
    expect(() => parseOpsSummary({ ...OPS, cases_by_kind: { ...OPS.cases_by_kind, DISPUTE: 2 } })).toThrowError(VIOLATION)
    expect(() => parseOpsSummary({ ...OPS, claims_today: { ...OPS.claims_today, automatic_share_pct: 99 } })).toThrowError(VIOLATION)
    expect(() => parseOpsSummary({ ...OPS, payouts_today: { ...OPS.payouts_today, credited_label: '₹4,25,421' } })).toThrowError(VIOLATION)
    expect(() => parseOpsSummary({ ...OPS, payouts_today: { ...OPS.payouts_today, credited_count: 311 } })).toThrowError(VIOLATION)
    expect(() => parseOpsSummary({ ...OPS, next_due_case: null })).toThrowError(VIOLATION)
    expect(() => parseOpsSummary(null)).toThrowError(VIOLATION)
  })
})

const side = (over: object) => ({ alert: 'NONE', alert_id: null, hourly_index_pct: [59, 58, 67], window_index_pct: 61, shops_in_index: 62, already_triggered_today: false, fires: false, status: 'slow_day', ...over })
const condition = (code: string, baseline: boolean, scenario: boolean) => ({ code, label_en: code, required: 'x', baseline: { met: baseline, observed: 'o' }, scenario: { met: scenario, observed: 'o' }, sources: [] })
const CODES = ['ALERT_COVERS_WINDOW', 'HOURS_BELOW_FLOOR', 'WINDOW_BELOW_BOUND', 'SHOPS_QUORUM', 'FIRST_TRIGGER_TODAY']
const WHATIF = {
  read_only: true,
  zone_id: 'Z9',
  zone_name: 'Chembur',
  at: '2025-08-19T17:00:00+05:30',
  window: { start: '2025-08-19T14:00:00+05:30', end: '2025-08-19T17:00:00+05:30' },
  rules_version: 'pilot-0.1',
  fixed: { index_floor_pct: 50, consecutive_hours: 3, min_shops_in_index: 20, lower_bound_pct: 90 },
  baseline: side({}),
  scenario: side({ alert: 'RAIN', fires: true, status: 'triggered', drop_pct: 51 }),
  changed: ['alert'],
  conditions: CODES.map((code, i) => condition(code, i >= 2, true)),
  counterfactual: null,
  example: null,
  computed_by: 'policy engine, deterministic',
  stored: false,
}

describe('parseWhatIf', () => {
  it('accepts an answer whose sides agree with their conditions', () => {
    expect(parseWhatIf(WHATIF).scenario.fires).toBe(true)
  })

  it('refuses a verdict that its conditions do not make, a missing condition and a stored answer', () => {
    expect(() => parseWhatIf({ ...WHATIF, scenario: side({ fires: false }) })).toThrowError(VIOLATION)
    expect(() => parseWhatIf({ ...WHATIF, conditions: WHATIF.conditions.slice(1) })).toThrowError(VIOLATION)
    expect(() => parseWhatIf({ ...WHATIF, conditions: WHATIF.conditions.toReversed() })).toThrowError(VIOLATION)
    expect(() => parseWhatIf({ ...WHATIF, stored: true })).toThrowError(VIOLATION)
  })
})
