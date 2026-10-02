/** The strict parser of GET /api/evals/summary: the no-run example passes, and a number the plan does not allow is a contract violation. */
import { describe, expect, it } from 'vitest'

import { parseEvalsSummary } from './evals'

const IDS = ['intent', 'guard', 'ask', 'slips', 'voice', 'chain']
const noRun = () => ({ measured: false, run: null, suites: IDS.map((id) => ({ id, status: 'NOT_MEASURED', reason: 'no run stored', metrics: [] })) })

const metric = (over: Record<string, unknown> = {}) => ({
  id: 'slips.wrong_read_passes_gate', suite: 'slips', title: 'Wrong reads that pass the gate', k: 0, n: 120, value: 0,
  interval: { method: 'wilson', level: 0.95, low: 0, high: 0.031 }, direction: 'at_most', target: 0, target_source: 'proposed',
  meets_target: true, interval_clears_target: false, status: 'MET, WIDE INTERVAL', reason: null, ...over,
})
const measured = (m: Record<string, unknown>) => ({
  measured: true,
  run: { run_id: 'run-1', commit: 'abc', started_at: '2026-10-02T10:00:00+05:30', ended_at: '2026-10-02T10:20:00+05:30', data_origin: 'synthetic', held_out_sha256: ['00'], providers: [{ component: 'slips', mode: 'LIVE', provider: 'gemini', model: 'm' }] },
  suites: IDS.map((id) => (id === 'slips' ? { id, status: 'MEASURED', reason: null, metrics: [m] } : { id, status: 'NOT_MEASURED', reason: 'no key', metrics: [] })),
})

describe('parseEvalsSummary', () => {
  it('accepts the no-run response of data-model 5.10', () => {
    const parsed = parseEvalsSummary(noRun())
    expect(parsed.measured).toBe(false)
    expect(parsed.suites).toHaveLength(6)
  })

  it('accepts a not-measured metric with every value null, and a measured run with its k of n', () => {
    const empty: { measured: boolean; run: null; suites: unknown[] } = { ...noRun() }
    empty.suites[3] = { id: 'slips', status: 'NOT_MEASURED', reason: 'no run stored', metrics: [metric({ k: null, n: null, value: null, interval: { method: 'wilson', level: 0.95, low: null, high: null }, meets_target: null, interval_clears_target: null, status: 'NOT_MEASURED', reason: 'no run stored' })] }
    expect(parseEvalsSummary(empty).suites[3].metrics[0].k).toBeNull()
    const parsed = parseEvalsSummary(measured(metric()))
    expect(parsed.run?.providers[0]).toMatchObject({ mode: 'LIVE', provider: 'gemini' })
    expect(parsed.suites[3].metrics[0]).toMatchObject({ k: 0, n: 120, status: 'MET, WIDE INTERVAL' })
  })

  it.each([
    ['a number on a NOT_MEASURED metric', measured(metric({ status: 'NOT_MEASURED' }))],
    ['k above n', measured(metric({ k: 200 }))],
    ['a missed target that is also met', measured(metric({ status: 'MISSED' }))],
    ['a wide interval that clears the target', measured(metric({ interval_clears_target: true }))],
    ['a value with no k of n', measured(metric({ k: null, n: null }))],
    ['a metric of another suite', measured(metric({ suite: 'voice' }))],
    ['a status outside the list', measured(metric({ status: 'GREAT' }))],
    ['a run header with no run', { ...noRun(), measured: true }],
    ['a run with measured false', { ...measured(metric()), measured: false }],
    ['the wrong suite order', { ...noRun(), suites: noRun().suites.toReversed() }],
    ['a missing suite', { ...noRun(), suites: noRun().suites.slice(1) }],
  ])('rejects %s', (_name, body) => {
    expect(() => parseEvalsSummary(body)).toThrow(/evals|run|suite|metric/i)
  })
})
