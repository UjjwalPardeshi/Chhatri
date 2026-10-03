/**
 * Backtest (SPEC §18, deck slide 11): the headline result first (the same paired bars and facts
 * as the Overview), then the full trigger comparison and the per-zone loss ratios against the
 * ratio premiums are priced for (SPEC §9.7, from GET /api/policy). With the flag h24_whatif the
 * pricing simulator ("Price the cover", GET /api/pricing) closes the page, at /backtest#pricing.
 */
import type { BacktestReport } from '../api/types'
import { CompareTable } from '../components/backtest/CompareTable'
import { ZoneTable } from '../components/backtest/ZoneTable'
import { Feature } from '../components/common/Feature'
import { AsyncView } from '../components/common/Status'
import { PricingSection } from '../components/pricing/PricingSection'
import { ProofFacts, ProofPairs, triggerPair } from '../components/proof/ProofBars'
import { targetLossRatio } from '../lib/rules'
import { useLive } from '../state/live'
import { useAsync, type AsyncState } from '../state/useAsync'

/** Copy deck `console.backtest.caveat` (fs-08 13.3, proposed wording: review with the insurer before it ships). */
export const BACKTEST_CAVEAT = "The model's range is calibrated on simulated sales, so this backtest tests the rule, not accuracy on real shops."

function Report({ report, target }: { report: BacktestReport; target: number | null }) {
  const pair = triggerPair(report)
  return (
    <>
      {pair ? (
        <section className="card section backtest-hero" aria-label="Result">
          <h2>Chhatri vs a weather-only trigger</h2>
          <ProofPairs chhatri={pair.chhatri} weather={pair.weather} />
          <ProofFacts chhatri={pair.chhatri} personal={report.personal} />
        </section>
      ) : null}
      <p className="backtest-caveat">{BACKTEST_CAVEAT}</p>
      <div className="backtest-grid">
        <section className="card section">
          <h2>Every measure</h2>
          <CompareTable report={report} />
        </section>
        <section className="card section">
          <h2>Premiums vs payouts, per zone</h2>
          <ZoneTable zones={report.zones} target={target} />
        </section>
      </div>
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

/** Loaded or failed: either way its part of the page has rendered and will not change height on its own. */
const settled = (state: AsyncState<unknown>): boolean => state.data !== null || state.error !== null

export default function Backtest() {
  const { api } = useLive()
  const report = useAsync((signal) => api.backtest(signal), [api])
  const policy = useAsync((signal) => api.policy(signal), [api])
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
        {(data) => <Report report={data} target={targetLossRatio(policy.data?.rules)} />}
      </AsyncView>
      <Feature name="h24_whatif">
        <PricingSection pageReady={settled(report) && settled(policy)} />
      </Feature>
    </div>
  )
}
