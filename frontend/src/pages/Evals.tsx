/**
 * AI evaluation (H25, flag h25_evals; AI evaluation plan section 7.3, screens-and-flows 9.5): what the AI parts measured,
 * how many items it was and against which target, and NOT MEASURED when there was no run. A page in the style of
 * Backtest (`useAsync`, `AsyncView`). It shows nothing but what the stored run holds: with no run every suite says NOT
 * MEASURED with its reason and no number appears. A slide or pitch line that quotes a figure quotes what this page shows.
 */
import { AsyncView } from '../components/common/Status'
import { RunHeader, SuiteCard } from '../components/evals/EvalCards'
import { SYNTHETIC_BANNER } from '../components/evals/evalFormat'
import { useLive } from '../state/live'
import { useAsync } from '../state/useAsync'
import '../styles/evals.css'

export default function Evals() {
  const { api } = useLive()
  const summary = useAsync((signal) => api.evalsSummary(signal), [api])
  return (
    <div className="page">
      <header className="page__head">
        <div>
          <p className="eyebrow">Measured, not claimed</p>
          <h1>AI evaluation</h1>
          <AsyncView {...summary} label="Loading the evaluation…">
            {(data) => <RunHeader run={data.run} />}
          </AsyncView>
        </div>
      </header>
      <p data-testid="eval-banner" className="eval-banner" role="note">
        {SYNTHETIC_BANNER} <span className="muted">The plan: docs/04-engineering/ai-evaluation-plan.md</span>
      </p>
      <AsyncView {...summary} label="Loading the evaluation…">
        {(data) => (
          <>
            {data.measured ? null : <p data-testid="eval-none" className="muted">No run is stored, so every suite reads NOT MEASURED and no number is shown.</p>}
            <div className="eval-grid">
              {data.suites.map((suite) => (
                <SuiteCard key={suite.id} suite={suite} />
              ))}
            </div>
          </>
        )}
      </AsyncView>
    </div>
  )
}
