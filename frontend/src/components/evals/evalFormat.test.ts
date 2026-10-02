/** The wording rules of the /evals page: k of n with its interval, the zero target, no number when not measured. */
import { describe, expect, it } from 'vitest'

import type { EvalMetric } from '../../api/evals'
import { intervalText, targetText, valueText } from './evalFormat'

const metric = (over: Partial<EvalMetric> = {}): EvalMetric => ({
  id: 'slips.wrong_read_passes_gate', suite: 'slips', title: 'Wrong reads that pass the gate', k: 0, n: 120, value: 0,
  interval: { method: 'wilson', level: 0.95, low: 0, high: 0.031 }, direction: 'at_most', target: 0, target_source: 'proposed',
  meets_target: true, interval_clears_target: false, status: 'MET, WIDE INTERVAL', reason: null, p50_ms: null, p95_ms: null, within_target_share: null, ...over,
})

describe('valueText', () => {
  it('reads a clean run against a zero target as the plan says, never "none"', () => {
    expect(valueText(metric())).toBe('0 of 120, below the upper bound with 95% confidence')
  })

  it('reads any other measured value as k of n', () => {
    expect(valueText(metric({ k: 21, n: 21, direction: 'at_least', target: 0.95 }))).toBe('21 of 21')
    expect(valueText(metric({ k: 2, n: 120 }))).toBe('2 of 120')
  })

  it('shows no number for a metric that was not measured', () => {
    expect(valueText(metric({ k: null, n: null, value: null, status: 'NOT_MEASURED' }))).toBeNull()
  })

  it('reads a latency metric as p50, p95 and the share within the target', () => {
    expect(valueText(metric({ k: null, n: null, value: null, p50_ms: 812.4, p95_ms: 2100, within_target_share: 0.9, target: 3000 }))).toBe('p50 812 ms, p95 2100 ms, 90.0% within the target')
  })
})

describe('intervalText and targetText', () => {
  it('writes the Wilson interval with its level, and none without one', () => {
    expect(intervalText(metric())).toBe('interval 0.0% to 3.1% (95%, wilson)')
    expect(intervalText(metric({ status: 'NOT_MEASURED', interval: { method: 'wilson', level: 0.95, low: null, high: null } }))).toBeNull()
  })

  it('writes the target with its source, and nothing when there is none', () => {
    expect(targetText(metric())).toBe('target 0 (proposed)')
    expect(targetText(metric({ direction: 'at_least', target: 0.95, target_source: 'PRD' }))).toBe('target at least 95.0% (PRD)')
    expect(targetText(metric({ target: null, target_source: null }))).toBeNull()
  })
})
