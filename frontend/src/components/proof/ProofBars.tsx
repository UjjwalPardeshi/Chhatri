/**
 * Backtest proof (deck slide 11, SPEC §18): Chhatri's trigger against a weather-only trigger over
 * two past monsoons, as paired bars on one 0-100% axis with direct labels (no tracks), plus the
 * three same-day facts. Shared by the Overview and /backtest so both read the same.
 *
 * Wording follows the deck ("More than a weather-only trigger", "Doubtful personal claims seen by
 * a human: all of them") and every number beside it comes from GET /api/backtest. "All of them" is
 * the policy's guarantee (SPEC §9.3: any SOFT fail or UNSURE is REFERRED, never paid alone); the
 * API gives the referred and auto-paid counts, not a separate doubtful count, so no share is shown.
 */
import type { BacktestReport, BacktestTrigger } from '../../api/types'

const PCT = 100

export type ProofMeasure = {
  label: string
  better: string
  /** How "more" and "less" read for this measure (deck slide 11: "More than" / "Fewer than"). */
  words: { more: string; less: string }
  value: (t: BacktestTrigger) => number
  detail: (t: BacktestTrigger) => string
}

const COUNT_WORDS = Object.freeze({ more: 'More', less: 'Fewer' })

export const PROOF_MEASURES: readonly ProofMeasure[] = [
  { label: 'Real sales drops that get paid', better: 'higher is better', words: COUNT_WORDS, value: (t) => t.recall, detail: (t) => `${t.real_drops_paid} of ${t.real_drops}` },
  { label: 'Payouts with no real drop', better: 'lower is better', words: COUNT_WORDS, value: (t) => t.false_positive_rate, detail: (t) => `${t.payouts_no_real_drop} of ${t.payouts}` },
]

/** Deck slide 11's target column, computed: "More than a weather-only trigger" when Chhatri's rate is higher. */
export function comparisonVerdict(measure: ProofMeasure, chhatri: BacktestTrigger, weather: BacktestTrigger): string {
  const ours = measure.value(chhatri)
  const theirs = measure.value(weather)
  if (ours === theirs) return 'The same as a weather-only trigger'
  return `${ours > theirs ? measure.words.more : measure.words.less} than a weather-only trigger`
}

export function pctLabel(value: number): string {
  return `${Math.round(value * PCT)}%`
}

/** Deck slide 11: doubtful personal claims seen by a human, "All of them" (SPEC §9.3 guarantees it). */
export function humanReviewLabel(personal: BacktestReport['personal']): string {
  return personal.referred === 0 ? 'None were doubtful' : 'All of them'
}

/** The counts behind it, as the API gives them. */
export function humanReviewDetail(personal: BacktestReport['personal']): string {
  return `${personal.referred} of ${personal.claims} personal claims sent to a human · ${personal.auto_paid} clean claims paid automatically`
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
      <p className="proof-pair__verdict">{comparisonVerdict(measure, chhatri, weather)}</p>
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
        <dd className="proof__sub">{humanReviewDetail(personal)}</dd>
      </div>
    </dl>
  )
}
