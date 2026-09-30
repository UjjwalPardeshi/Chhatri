/**
 * Policy (SPEC §9, §20 "Policy", deck slide 8): two independent columns, so neither leaves a
 * hole under a short card: the payout authority table and the checks on the left, the three live
 * tests and the rules (values in their units, ruleFormat.ts) on the right. Checks become one card
 * per check on a phone.
 */
import type { PolicyView } from '../api/types'
import { AsyncView } from '../components/common/Status'
import { authorityTone } from '../components/overview/Humans'
import { LiveTests } from '../components/overview/LiveTests'
import { ruleRows } from '../components/policy/ruleFormat'
import { useLive } from '../state/live'
import { useAsync } from '../state/useAsync'
import { useLaunch, type LaunchState } from '../state/useLaunch'

export { humanise, ruleRows } from '../components/policy/ruleFormat'

function Authority({ policy }: { policy: PolicyView }) {
  return (
    <section className="card section">
      <h2>Payout authority</h2>
      <table className="table authority">
        <thead>
          <tr>
            <th>Case</th>
            <th>Chhatri alone</th>
            <th>Goes to a human</th>
          </tr>
        </thead>
        <tbody>
          {policy.authority.map((row) => (
            <tr key={row.case}>
              <td>{row.case}</td>
              <td className={authorityTone(row.alone)}>{row.alone}</td>
              <td>{row.human}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        New cover starts only after a <strong>waiting period</strong>, so nobody can buy it once a storm is forecast.
      </p>
    </section>
  )
}

function Checks({ policy }: { policy: PolicyView }) {
  return (
    <section className="card section">
      <h2>Checks before any payout</h2>
      <table className="table policy-checks">
        <thead>
          <tr>
            <th>Check</th>
            <th>Applies</th>
            <th>Severity</th>
            <th>Passes when</th>
          </tr>
        </thead>
        <tbody>
          {policy.checks.map((c) => (
            <tr key={c.code}>
              <td className="mono policy-checks__code">{c.code}</td>
              <td data-label="Applies">{c.applies}</td>
              <td className="policy-checks__severity">
                <span className={`badge ${c.severity === 'HARD' ? 'badge--navy' : 'badge--amber'}`}>{c.severity}</span>
              </td>
              <td data-label="Passes when">{c.passes_when}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Rules({ policy }: { policy: PolicyView }) {
  return (
    <section className="card section">
      <h2>Rules</h2>
      <dl className="rules">
        {ruleRows(policy.rules).map(([k, v]) => (
          <div key={k} className="rules__row">
            <dt>{k}</dt>
            <dd className="num">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function PolicyContent({ policy, launcher }: { policy: PolicyView; launcher: LaunchState }) {
  return (
    <div className="policy-grid">
      <div className="policy-grid__col">
        <Authority policy={policy} />
        <Checks policy={policy} />
      </div>
      <div className="policy-grid__col">
        <LiveTests launcher={launcher} />
        <Rules policy={policy} />
      </div>
    </div>
  )
}

export default function Policy() {
  const { api } = useLive()
  const launcher = useLaunch()
  const policy = useAsync((signal) => api.policy(signal), [api])
  return (
    <div className="page">
      <header className="page__head">
        <div>
          <p className="eyebrow">Humans in control</p>
          <h1>Automatic when the data is clear, human when it isn’t</h1>
          <p className="muted">Only the policy engine can approve money. The AI builds the case; code checks every payout against these rules.</p>
        </div>
      </header>
      <AsyncView {...policy} label="Loading policy…">
        {(data) => <PolicyContent policy={data} launcher={launcher} />}
      </AsyncView>
    </div>
  )
}
