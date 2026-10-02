/**
 * The parts of the /evals page (screens-and-flows 9.5): the run header with one chip for each provider configuration, a
 * status chip with a glyph and its word (colour is never the only signal), a metric row and a suite card. A suite that
 * was not measured says why and shows no number; configurations are separate chips and are never averaged.
 */
import type { EvalMetric, EvalRun, EvalSuite, MetricStatus } from '../../api/evals'
import { ModeWord } from '../common/ModeChip'
import { intervalText, METRIC_STATUS_LABEL, SUITE_STATUS_LABEL, SUITE_TITLES, targetText, valueText } from './evalFormat'

const TONE: Readonly<Record<MetricStatus, { badge: string; glyph: string }>> = {
  NOT_MEASURED: { badge: 'badge--grey', glyph: '○' },
  MISSED: { badge: 'badge--red', glyph: '✕' },
  'MET, WIDE INTERVAL': { badge: 'badge--amber', glyph: '▲' },
  MET: { badge: 'badge--green', glyph: '✓' },
}

export function StatusChip({ status, testId }: { status: MetricStatus; testId?: string }) {
  const { badge, glyph } = TONE[status]
  return (
    <span className={`badge ${badge}`} data-testid={testId} data-status={status}>
      <span aria-hidden="true">{glyph}</span> {METRIC_STATUS_LABEL[status]}
    </span>
  )
}

export function RunHeader({ run }: { run: EvalRun | null }) {
  if (run === null) return <p data-testid="eval-run" className="muted">Run: none stored</p>
  return (
    <div data-testid="eval-run" className="eval-run">
      <p>
        <strong>Run {run.run_id}</strong> · commit <span className="mono">{run.commit}</span>
        {run.started_at ? ` · started ${run.started_at}` : ''}
        {run.ended_at ? ` · ended ${run.ended_at}` : ''} · data origin: {run.data_origin}
      </p>
      <ul className="eval-providers" aria-label="Provider configurations used">
        {run.providers.map((provider) => (
          <li key={`${provider.component}-${provider.provider}`} data-testid="eval-provider">
            <ModeWord mode={provider.mode} /> {provider.component} · {provider.provider}
            {provider.model ? ` · ${provider.model}` : ''}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function MetricRow({ metric }: { metric: EvalMetric }) {
  const value = valueText(metric)
  const interval = intervalText(metric)
  const target = targetText(metric)
  return (
    <li data-testid="eval-metric" data-metric={metric.id} data-status={metric.status} className="eval-metric">
      <div className="eval-metric__main">
        <span className="eval-metric__title">{metric.title}</span>
        <StatusChip status={metric.status} />
      </div>
      {value ? <span data-testid="eval-value" className="eval-metric__value">{value}</span> : null}
      {interval ? <span className="muted">{interval}</span> : null}
      {target ? <span className="muted">{target}</span> : null}
      {metric.reason ? <span className="muted">{metric.reason}</span> : null}
    </li>
  )
}

export function SuiteCard({ suite }: { suite: EvalSuite }) {
  const tone = suite.status === 'MEASURED' ? 'badge--green' : suite.status === 'PARTIAL' ? 'badge--amber' : 'badge--grey'
  return (
    <section data-testid={`eval-suite-${suite.id}`} data-status={suite.status} className="card section eval-suite">
      <h2>{SUITE_TITLES[suite.id]}</h2>
      <p>
        <span className={`badge ${tone}`}>{SUITE_STATUS_LABEL[suite.status]}</span>
        {suite.reason ? <span className="muted"> {suite.reason}</span> : null}
      </p>
      {suite.metrics.length > 0 ? (
        <ul className="eval-metrics">
          {suite.metrics.map((metric) => (
            <MetricRow key={metric.id} metric={metric} />
          ))}
        </ul>
      ) : null}
    </section>
  )
}
