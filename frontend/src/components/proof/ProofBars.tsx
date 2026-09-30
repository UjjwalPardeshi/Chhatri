/**
 * Backtest proof (deck slide 11, SPEC §18): Chhatri's trigger against a weather-only trigger over
 * two past monsoons, as paired bars on one 0-100% axis with direct labels (no tracks), plus the
 * three same-day facts. Shared by the Overview and /backtest so both read the same.
 */
import type { BacktestReport, BacktestTrigger } from '../../api/types'

const PCT = 100

export type ProofMeasure = { label: string; better: string; value: (t: BacktestTrigger) => number; detail: (t: BacktestTrigger) => string }

export const PROOF_MEASURES: readonly ProofMeasure[] = [
  { label: 'Real sales drops that get paid', better: 'higher is better', value: (t) => t.recall, detail: (t) => `${t.real_drops_paid} of ${t.real_drops}` },
  { label: 'Payouts with no real drop', better: 'lower is better', value: (t) => t.false_positive_rate, detail: (t) => `${t.payouts_no_real_drop} of ${t.payouts}` },
]

export function pctLabel(value: number): string {
  return `${Math.round(value * PCT)}%`
}

/** SPEC §18: every doubtful personal claim goes to a human, so the share seen is referred / referred. */
export function humanReviewLabel(personal: BacktestReport['personal']): string {
  if (personal.referred === 0) return 'none were doubtful'
  return `all ${personal.referred} (${pctLabel(personal.referred / personal.referred)})`
}

export function triggerPair(report: BacktestReport): { chhatri: BacktestTrigger; weather: BacktestTrigger } | null {
  const chhatri = report.triggers.find((t) => t.name === 'chhatri')
  const weather = report.triggers.find((t) => t.name === 'weather_only')
  return chhatri && weather ? { chhatri, weather } : null
}

function Pair({ measure, chhatri, weather }: { measure: ProofMeasure; chhatri: BacktestTrigger; weather: BacktestTrigger }) {
  const rows = [
    { name: 'Chhatri', t: chhatri, ours: true },
    { name: 'Weather-only', t: weather, ours: false },
  ]
  return (
    <figure className="proof-pair" aria-label={measure.label}>
      <figcaption>
        <strong>{measure.label}</strong> <span className="muted">{measure.better}</span>
      </figcaption>
      {rows.map((r) => (
        <div key={r.name} className={`proof-bar ${r.ours ? 'proof-bar--ours' : ''}`} title={`${r.name}: ${measure.detail(r.t)} (${pctLabel(measure.value(r.t))})`}>
          <span className="proof-bar__name">{r.name}</span>
          <span className="proof-bar__track">
            <span className="proof-bar__fill" style={{ width: `${Math.min(PCT, measure.value(r.t) * PCT)}%` }} />
          </span>
          <span className="proof-bar__value num">
            <strong>{pctLabel(measure.value(r.t))}</strong> <span className="muted">{measure.detail(r.t)}</span>
          </span>
        </div>
      ))}
    </figure>
  )
}

export function ProofPairs({ chhatri, weather }: { chhatri: BacktestTrigger; weather: BacktestTrigger }) {
  return (
    <div className="proof__pairs">
      {PROOF_MEASURES.map((m) => (
        <Pair key={m.label} measure={m} chhatri={chhatri} weather={weather} />
      ))}
    </div>
  )
}

export function ProofFacts({ chhatri, personal }: { chhatri: BacktestTrigger; personal: BacktestReport['personal'] }) {
  return (
    <dl className="proof__facts">
      <div>
        <dt>Trigger to money</dt>
        <dd className="num">{chhatri.trigger_to_money}</dd>
      </div>
      <div>
        <dt>Documents per area claim</dt>
        <dd className="num">{chhatri.documents_per_area_claim}</dd>
      </div>
      <div>
        <dt>Doubtful personal claims seen by a human</dt>
        <dd className="num">{humanReviewLabel(personal)}</dd>
        <dd className="proof__sub">{personal.auto_paid} clean claims paid automatically</dd>
      </div>
    </dl>
  )
}
