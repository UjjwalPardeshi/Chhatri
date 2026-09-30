/**
 * Backtest proof on the Overview (deck slide 11, SPEC §18), read live from GET /api/backtest and
 * drawn with the same bars as /backtest.
 */
import { Link } from 'react-router'

import type { BacktestReport } from '../../api/types'
import { useLive } from '../../state/live'
import { useAsync } from '../../state/useAsync'
import { AsyncView } from '../common/Status'
import { ProofFacts, ProofPairs, triggerPair } from '../proof/ProofBars'
import { RevealSection } from './Reveal'

export { pctLabel, PROOF_MEASURES } from '../proof/ProofBars'

function ProofBody({ report }: { report: BacktestReport }) {
  const pair = triggerPair(report)
  if (!pair) return <p className="muted">The backtest report has no trigger comparison yet.</p>
  return (
    <div className="proof">
      <ProofPairs chhatri={pair.chhatri} weather={pair.weather} />
      <ProofFacts chhatri={pair.chhatri} personal={report.personal} />
      <p className="ov-source">
        <span className="badge badge--amber">{report.label}</span> {report.seasons.join(' · ')} · <Link to="/backtest">Full report and per-zone loss ratios</Link>
      </p>
    </div>
  )
}

export function Proof() {
  const { api } = useLive()
  const report = useAsync((signal) => api.backtest(signal), [api])
  return (
    <RevealSection label="Backtest" id="ov-proof" className="ov-proof">
      <h2 className="ov-h2">Backtest first: two past monsoons, replayed.</h2>
      <AsyncView {...report} label="Loading the backtest…">
        {(data) => <ProofBody report={data} />}
      </AsyncView>
    </RevealSection>
  )
}
