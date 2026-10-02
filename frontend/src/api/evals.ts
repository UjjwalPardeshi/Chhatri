/**
 * Types and the strict parser of GET /api/evals/summary (H25, data-model 5.10, AI evaluation plan section 7). The page
 * shows nothing but what was measured, so the parser holds the plan's own rules: a metric that is NOT_MEASURED carries
 * no number, a measured one carries its k of n, and a status never contradicts the numbers beside it. A body that
 * breaks a rule raises `ContractViolation` and the page shows its error state. Keys the plan marks as proposed (the
 * run header, the latency share) are read when present and never required; unknown extra keys are ignored.
 */
import { ContractViolation } from '../miniapp/api/parse'

export const SUITE_IDS = ['intent', 'guard', 'ask', 'slips', 'voice', 'chain'] as const
export const SUITE_STATUSES = ['MEASURED', 'PARTIAL', 'NOT_MEASURED'] as const
export const METRIC_STATUSES = ['NOT_MEASURED', 'MISSED', 'MET, WIDE INTERVAL', 'MET'] as const
export const EVAL_MODES = ['LIVE', 'SIMULATED', 'FALLBACK'] as const

export type SuiteId = (typeof SUITE_IDS)[number]
export type SuiteStatus = (typeof SUITE_STATUSES)[number]
export type MetricStatus = (typeof METRIC_STATUSES)[number]
export type EvalMode = (typeof EVAL_MODES)[number]

export type MetricInterval = { method: string; level: number | null; low: number | null; high: number | null }
export type EvalMetric = {
  id: string
  suite: SuiteId
  title: string
  k: number | null
  n: number | null
  value: number | null
  interval: MetricInterval
  direction: 'at_least' | 'at_most' | null
  target: number | null
  target_source: string | null
  meets_target: boolean | null
  interval_clears_target: boolean | null
  status: MetricStatus
  reason: string | null
  p50_ms: number | null
  p95_ms: number | null
  within_target_share: number | null
}
export type EvalSuite = { id: SuiteId; status: SuiteStatus; reason: string | null; metrics: EvalMetric[] }
export type EvalProvider = { component: string; mode: EvalMode; provider: string; model: string | null }
export type EvalRun = {
  run_id: string
  commit: string
  started_at: string | null
  ended_at: string | null
  data_origin: string
  held_out_sha256: string[]
  providers: EvalProvider[]
}
export type EvalsSummary = { measured: boolean; run: EvalRun | null; suites: EvalSuite[] }

type Json = Readonly<Record<string, unknown>>

const isNil = (value: unknown): boolean => value === null || value === undefined

function fail(path: string, problem: string): never {
  throw new ContractViolation(`${path}: ${problem}`)
}

function record(value: unknown, path: string, required: readonly string[]): Json {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'expected an object')
  const found = value as Json
  const missing = required.filter((key) => !(key in found))
  if (missing.length > 0) fail(path, `missing field ${missing.join(', ')}`)
  return found
}

const list = (value: unknown, path: string): readonly unknown[] => (Array.isArray(value) ? value : fail(path, 'expected a list'))

function str(source: Json, key: string, path: string): string {
  const value = source[key]
  return typeof value === 'string' ? value : fail(`${path}.${key}`, 'expected text')
}
const strOrNull = (source: Json, key: string, path: string): string | null => (isNil(source[key]) ? null : str(source, key, path))

function num(source: Json, key: string, path: string): number | null {
  const value = source[key]
  if (isNil(value)) return null
  return typeof value === 'number' && Number.isFinite(value) ? value : fail(`${path}.${key}`, 'expected a number or null')
}

function count(source: Json, key: string, path: string): number | null {
  const value = num(source, key, path)
  return value === null || (Number.isInteger(value) && value >= 0) ? value : fail(`${path}.${key}`, 'expected a whole number')
}

function oneOf<T extends string>(source: Json, key: string, path: string, allowed: readonly T[]): T {
  const value = source[key]
  return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? (value as T) : fail(`${path}.${key}`, `expected one of ${allowed.join(', ')}`)
}

function flag(source: Json, key: string, path: string): boolean | null {
  const value = source[key]
  if (isNil(value)) return null
  return typeof value === 'boolean' ? value : fail(`${path}.${key}`, 'expected true, false or null')
}

function parseInterval(raw: unknown, path: string): MetricInterval {
  const source = record(raw, path, ['method', 'low', 'high'])
  const low = num(source, 'low', path)
  const high = num(source, 'high', path)
  if ((low === null) !== (high === null)) fail(path, 'low and high are both numbers or both null')
  if (low !== null && high !== null && low > high) fail(path, 'low is above high')
  return { method: str(source, 'method', path), level: num(source, 'level', path), low, high }
}

/** The plan's rule 1: a number comes with its k of n, and a status never contradicts the numbers. */
function checkConsistency(metric: EvalMetric, path: string): void {
  const measured = metric.status !== 'NOT_MEASURED'
  const hasNumber = metric.value !== null || metric.k !== null || metric.p50_ms !== null
  if (!measured && (hasNumber || metric.interval.low !== null)) fail(path, 'a metric that is NOT_MEASURED carries no number')
  if (measured && metric.value !== null && (metric.k === null || metric.n === null) && metric.p50_ms === null) fail(path, 'a measured value needs its k of n')
  if (metric.k !== null && metric.n !== null && metric.k > metric.n) fail(path, 'k is above n')
  if (metric.status === 'MET, WIDE INTERVAL' && metric.interval_clears_target === true) fail(path, 'a wide interval cannot clear the target')
  if (metric.status === 'MISSED' && metric.meets_target === true) fail(path, 'a missed target cannot be met')
}

function parseMetric(raw: unknown, path: string, suite: SuiteId): EvalMetric {
  const source = record(raw, path, ['id', 'suite', 'title', 'status', 'interval'])
  const metricSuite = oneOf(source, 'suite', path, SUITE_IDS)
  if (metricSuite !== suite) fail(`${path}.suite`, `expected ${suite}`)
  const direction = isNil(source.direction) ? null : oneOf(source, 'direction', path, ['at_least', 'at_most'] as const)
  const metric: EvalMetric = {
    id: str(source, 'id', path),
    suite: metricSuite,
    title: str(source, 'title', path),
    k: count(source, 'k', path),
    n: count(source, 'n', path),
    value: num(source, 'value', path),
    interval: parseInterval(source.interval, `${path}.interval`),
    direction,
    target: num(source, 'target', path),
    target_source: strOrNull(source, 'target_source', path),
    meets_target: flag(source, 'meets_target', path),
    interval_clears_target: flag(source, 'interval_clears_target', path),
    status: oneOf(source, 'status', path, METRIC_STATUSES),
    reason: strOrNull(source, 'reason', path),
    p50_ms: num(source, 'p50_ms', path),
    p95_ms: num(source, 'p95_ms', path),
    within_target_share: num(source, 'within_target_share', path) ?? num(source, 'share_within_target', path),
  }
  checkConsistency(metric, path)
  return metric
}

function parseSuite(raw: unknown, path: string): EvalSuite {
  const source = record(raw, path, ['id', 'status', 'metrics'])
  const id = oneOf(source, 'id', path, SUITE_IDS)
  const status = oneOf(source, 'status', path, SUITE_STATUSES)
  const reason = strOrNull(source, 'reason', path)
  const metrics = list(source.metrics, `${path}.metrics`).map((entry, index) => parseMetric(entry, `${path}.metrics[${index}]`, id))
  if (status === 'NOT_MEASURED' && metrics.some((metric) => metric.status !== 'NOT_MEASURED')) fail(path, 'a suite that is NOT_MEASURED holds no measured metric')
  if (status === 'NOT_MEASURED' && reason === null) fail(`${path}.reason`, 'a suite that is NOT_MEASURED says why')
  return { id, status, reason, metrics }
}

function parseProvider(raw: unknown, path: string): EvalProvider {
  const source = record(raw, path, ['component', 'mode', 'provider'])
  return { component: str(source, 'component', path), mode: oneOf(source, 'mode', path, EVAL_MODES), provider: str(source, 'provider', path), model: strOrNull(source, 'model', path) }
}

function parseRun(raw: unknown): EvalRun {
  const path = 'run'
  const source = record(raw, path, ['run_id', 'data_origin'])
  const hashes = source.held_out_sha256
  return {
    run_id: str(source, 'run_id', path),
    commit: strOrNull(source, 'commit', path) ?? 'unknown',
    started_at: strOrNull(source, 'started_at', path),
    ended_at: strOrNull(source, 'ended_at', path),
    data_origin: str(source, 'data_origin', path),
    held_out_sha256: isNil(hashes) ? [] : list(hashes, `${path}.held_out_sha256`).map((hash, index) => (typeof hash === 'string' ? hash : fail(`${path}.held_out_sha256[${index}]`, 'expected text'))),
    providers: isNil(source.providers) ? [] : list(source.providers, `${path}.providers`).map((entry, index) => parseProvider(entry, `${path}.providers[${index}]`)),
  }
}

export function parseEvalsSummary(raw: unknown): EvalsSummary {
  const source = record(raw, 'evals', ['measured', 'run', 'suites'])
  if (typeof source.measured !== 'boolean') fail('evals.measured', 'expected true or false')
  const suites = list(source.suites, 'evals.suites').map((entry, index) => parseSuite(entry, `evals.suites[${index}]`))
  if (suites.length !== SUITE_IDS.length || SUITE_IDS.some((id, index) => suites[index].id !== id)) fail('evals.suites', 'expected the six suites in the order of the plan')
  const run = isNil(source.run) ? null : parseRun(source.run)
  if (source.measured !== (run !== null)) fail('evals.run', 'a run header exists exactly when measured is true')
  if (!source.measured && suites.some((suite) => suite.status !== 'NOT_MEASURED')) fail('evals.suites', 'with no run every suite is NOT_MEASURED')
  return { measured: source.measured, run, suites }
}

export const EVALS_PATH = '/api/evals/summary'
