/**
 * How the /evals page words a measurement (AI evaluation plan section 3): the value is always "k of n", never a bare
 * percentage; an interval comes with it; a target of 0 is never "none" and a clean run reads "0 of n, below the upper
 * bound with 95% confidence"; a metric that was not measured shows no number at all. Pure functions, so the rules are
 * tested without a page.
 */
import type { EvalMetric, MetricStatus, SuiteId, SuiteStatus } from '../../api/evals'

/** The six suites in the plan's order, S1 to S6 (not the mini-app screens S1 to S11 of the design deck). */
export const SUITE_TITLES: Readonly<Record<SuiteId, string>> = {
  intent: 'S1 Intent routing',
  guard: 'S2 Guard red-team',
  ask: 'S3 Ask end to end',
  slips: 'S4 Slip reading and the gate',
  voice: 'S5 Voice',
  chain: 'S6 Chains and labels',
}

export const SUITE_STATUS_LABEL: Readonly<Record<SuiteStatus, string>> = { MEASURED: 'MEASURED', PARTIAL: 'PARTIAL', NOT_MEASURED: 'NOT MEASURED' }

export const METRIC_STATUS_LABEL: Readonly<Record<MetricStatus, string>> = {
  NOT_MEASURED: 'NOT MEASURED',
  MEASURED: 'MEASURED',
  MISSED: 'MISSED',
  'MET, WIDE INTERVAL': 'MET, WIDE INTERVAL',
  MET: 'MET',
}

export const SYNTHETIC_BANNER = 'Synthetic data only. Results on generated slips and written questions say little about real merchants or real hospital paper.'

const PERCENT = 100

/** A rate as a percentage with one decimal: 0.031 is "3.1%". Only ever shown beside its k of n. */
export function percent(rate: number): string {
  return `${(rate * PERCENT).toFixed(1)}%`
}

export const isLatency = (metric: EvalMetric): boolean => metric.p50_ms !== null || metric.p95_ms !== null

/** The value of a metric in words, or null when it was not measured (no number is invented). */
export function valueText(metric: EvalMetric): string | null {
  if (metric.status === 'NOT_MEASURED') return null
  if (isLatency(metric)) {
    const parts = [metric.p50_ms === null ? null : `p50 ${Math.round(metric.p50_ms)} ms`, metric.p95_ms === null ? null : `p95 ${Math.round(metric.p95_ms)} ms`]
    const share = metric.within_target_share === null ? null : `${percent(metric.within_target_share)} within the target`
    return [...parts, share].filter((part): part is string => part !== null).join(', ')
  }
  if (metric.k === null || metric.n === null) return null
  if (metric.k === 0 && metric.target === 0 && metric.direction === 'at_most') return `0 of ${metric.n}, below the upper bound with 95% confidence`
  return `${metric.k} of ${metric.n}`
}

/** "interval 0.0% to 3.1% (95%, wilson)", or null when there is none. */
export function intervalText(metric: EvalMetric): string | null {
  const { low, high, level, method } = metric.interval
  if (metric.status === 'NOT_MEASURED' || low === null || high === null) return null
  const confidence = level === null ? '' : `${Math.round(level * PERCENT)}%, `
  return `interval ${percent(low)} to ${percent(high)} (${confidence}${method})`
}

/** "target 0 (proposed)" or "target at least 95% (PRD)": the target with its source, or null when the metric has no target. */
export function targetText(metric: EvalMetric): string | null {
  if (metric.target === null) return null
  const rate = metric.n !== null && metric.target > 0 && metric.target <= 1
  const shown = isLatency(metric) ? `${metric.target} ms` : rate ? percent(metric.target) : String(metric.target)
  const side = metric.direction === 'at_least' ? 'at least ' : metric.direction === 'at_most' && metric.target !== 0 ? 'at most ' : ''
  const source = metric.target_source === null ? '' : ` (${metric.target_source})`
  return `target ${side}${shown}${source}`
}
