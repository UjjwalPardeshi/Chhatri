/**
 * The full trigger comparison (SPEC §18 metrics, deck slide 11): every measure for Chhatri and the
 * weather-only trigger side by side, the better value in green where "better" has a direction.
 */
import type { BacktestReport, BacktestTrigger } from '../../api/types'
import { formatInr } from '../../lib/money'
import { humanReviewDetail, humanReviewLabel, pctLabel } from '../proof/ProofBars'

type Metric = { label: string; value: (t: BacktestTrigger) => string; better: 'high' | 'low' | null; score: (t: BacktestTrigger) => number }

export const METRICS: readonly Metric[] = [
  { label: 'Real sales drops that get paid', value: (t) => `${t.real_drops_paid} of ${t.real_drops} (${pctLabel(t.recall)})`, better: 'high', score: (t) => t.recall },
  { label: 'Payouts with no real drop', value: (t) => `${t.payouts_no_real_drop} of ${t.payouts} (${pctLabel(t.false_positive_rate)})`, better: 'low', score: (t) => t.false_positive_rate },
  { label: 'Trigger to money', value: (t) => t.trigger_to_money, better: null, score: () => 0 },
  { label: 'Documents per area claim', value: (t) => String(t.documents_per_area_claim), better: null, score: () => 0 },
  { label: 'Total paid', value: (t) => formatInr(t.paid_paise), better: null, score: () => 0 },
]

export function winner(metric: Metric, triggers: readonly BacktestTrigger[]): string | null {
  if (!metric.better || triggers.length < 2) return null
  const sorted = triggers.toSorted((a, b) => (metric.better === 'high' ? metric.score(b) - metric.score(a) : metric.score(a) - metric.score(b)))
  return metric.score(sorted[0]) === metric.score(sorted[1]) ? null : sorted[0].name
}

export function CompareTable({ report }: { report: BacktestReport }) {
  const columns = (['chhatri', 'weather_only'] as const).map((name) => report.triggers.find((t) => t.name === name)).filter((t): t is BacktestTrigger => t !== undefined)
  return (
    <table className="table compare">
      <thead>
        <tr>
          <th>Measure</th>
          {columns.map((t) => (
            <th key={t.name} className={`compare__col ${t.name === 'chhatri' ? 'compare__us' : ''}`}>
              {t.name === 'chhatri' ? 'Chhatri' : 'Weather-only'}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {METRICS.map((metric) => {
          const best = winner(metric, columns)
          return (
            <tr key={metric.label}>
              <td>{metric.label}</td>
              {columns.map((t) => (
                <td key={t.name} className={`compare__col num ${t.name === 'chhatri' ? 'compare__us-cell' : ''} ${best === t.name ? 'compare__best' : ''}`}>
                  {metric.value(t)}
                </td>
              ))}
            </tr>
          )
        })}
        <tr>
          <td>Doubtful personal claims seen by a human</td>
          <td className="compare__col compare__us-cell compare__best num" colSpan={columns.length}>
            {humanReviewLabel(report.personal)} · {humanReviewDetail(report.personal)}
          </td>
        </tr>
      </tbody>
    </table>
  )
}
