/** Backtest (SPEC §18, deck slide 11): Chhatri vs a weather-only trigger, per-zone loss ratios. */
import type { BacktestReport, BacktestTrigger } from '../api/types'
import { AsyncView } from '../components/common/Status'
import { formatInr } from '../lib/money'
import { useLive } from '../state/live'
import { useAsync } from '../state/useAsync'

const PCT = 100

export function pct(value: number): string {
  return `${Math.round(value * PCT)}%`
}

type Metric = { label: string; value: (t: BacktestTrigger) => string; better: 'high' | 'low' | null; score: (t: BacktestTrigger) => number }

export const METRICS: readonly Metric[] = [
  { label: 'Real sales drops that get paid', value: (t) => `${t.real_drops_paid} of ${t.real_drops} (${pct(t.recall)})`, better: 'high', score: (t) => t.recall },
  { label: 'Payouts with no real drop', value: (t) => `${t.payouts_no_real_drop} of ${t.payouts} (${pct(t.false_positive_rate)})`, better: 'low', score: (t) => t.false_positive_rate },
  { label: 'Trigger to money', value: (t) => t.trigger_to_money, better: null, score: () => 0 },
  { label: 'Documents per area claim', value: (t) => String(t.documents_per_area_claim), better: null, score: () => 0 },
  { label: 'Total paid', value: (t) => formatInr(t.paid_paise), better: null, score: () => 0 },
]

function winner(metric: Metric, triggers: readonly BacktestTrigger[]): string | null {
  if (!metric.better || triggers.length < 2) return null
  const sorted = triggers.toSorted((a, b) => (metric.better === 'high' ? metric.score(b) - metric.score(a) : metric.score(a) - metric.score(b)))
  return metric.score(sorted[0]) === metric.score(sorted[1]) ? null : sorted[0].name
}

function Report({ report }: { report: BacktestReport }) {
  const chhatri = report.triggers.find((t) => t.name === 'chhatri')
  const weather = report.triggers.find((t) => t.name === 'weather_only')
  const columns = [chhatri, weather].filter((t): t is BacktestTrigger => t !== undefined)
  const maxRatio = Math.max(1, ...report.zones.map((z) => z.loss_ratio))
  return (
    <>
      <section className="card section">
        <h2>Chhatri vs a weather-only trigger</h2>
        <table className="table compare">
          <thead>
            <tr>
              <th>Measure</th>
              {columns.map((t) => (
                <th key={t.name} className={t.name === 'chhatri' ? 'compare__us' : ''}>
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
                    <td key={t.name} className={`num ${best === t.name ? 'compare__best' : ''}`}>
                      {metric.value(t)}
                    </td>
                  ))}
                </tr>
              )
            })}
            <tr>
              <td>Doubtful personal claims seen by a human</td>
              <td className="num compare__best" colSpan={columns.length}>
                {report.personal.referred} of {report.personal.claims} referred ({pct(report.personal.referred_share)}) · {report.personal.auto_paid} paid automatically
              </td>
            </tr>
          </tbody>
        </table>
      </section>
      <section className="card section">
        <h2>Premiums vs payouts, per zone</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Zone</th>
              <th className="num">Premium / day</th>
              <th className="num">Premiums</th>
              <th className="num">Payouts</th>
              <th>Loss ratio</th>
              <th className="num">False +</th>
              <th className="num">Missed</th>
            </tr>
          </thead>
          <tbody>
            {report.zones.map((z) => (
              <tr key={z.zone_id}>
                <td>{z.zone_id}</td>
                <td className="num">{z.premium_per_day_label}</td>
                <td className="num">{formatInr(z.premiums_paise)}</td>
                <td className="num">{formatInr(z.payouts_paise)}</td>
                <td aria-label={`Loss ratio ${pct(z.loss_ratio)}`}>
                  <span className="ratio">
                    <span className="ratio__bar" style={{ width: `${(z.loss_ratio / maxRatio) * 100}%` }} />
                    <span className="num">{pct(z.loss_ratio)}</span>
                  </span>
                </td>
                <td className="num">{z.chhatri_fp}</td>
                <td className="num">{z.chhatri_fn}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {report.notes.length > 0 ? (
        <ul className="notes muted">
          {report.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </>
  )
}

export default function Backtest() {
  const { api } = useLive()
  const report = useAsync((signal) => api.backtest(signal), [api])
  return (
    <div className="page">
      <header className="page__head">
        <div>
          <p className="eyebrow">Backtest · two past monsoons</p>
          <h1>Would Chhatri have paid the real losses?</h1>
          {report.data ? (
            <p className="muted">
              <span className="badge badge--amber">{report.data.label}</span> {report.data.seasons.join(' · ')}
            </p>
          ) : null}
        </div>
      </header>
      <AsyncView {...report} label="Loading backtest…">
        {(data) => <Report report={data} />}
      </AsyncView>
    </div>
  )
}
