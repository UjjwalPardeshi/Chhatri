/**
 * Backtest (SPEC §18, deck slide 11): the headline result first (the same paired bars and facts
 * as the Overview), then the full trigger comparison and the per-zone loss ratios against the
 * ratio premiums are priced for (SPEC §9.7, from GET /api/policy).
 */
import type { BacktestReport } from '../api/types'
import { CompareTable } from '../components/backtest/CompareTable'
import { ZoneTable } from '../components/backtest/ZoneTable'
import { AsyncView } from '../components/common/Status'
import { ProofFacts, ProofPairs, triggerPair } from '../components/proof/ProofBars'
import { targetLossRatio } from '../lib/rules'
import { useLive } from '../state/live'
import { useAsync } from '../state/useAsync'

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
    </div>
  )
}
