/** Policy (SPEC §9, §20 "Policy", deck slide 8): payout authority table, rules and checks. */
import type { PolicyView } from '../api/types'
import { AsyncView } from '../components/common/Status'
import { authorityTone } from '../components/overview/Humans'
import { LiveTests } from '../components/overview/LiveTests'
import { useLive } from '../state/live'
import { useAsync } from '../state/useAsync'
import { useLaunch, type LaunchState } from '../state/useLaunch'

export function humanise(key: string): string {
  const text = key.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Flattens nested rules into [section, key, value] rows. */
export function ruleRows(rules: Record<string, unknown>, prefix = ''): [string, string][] {
  return Object.entries(rules).flatMap(([key, value]) => {
    const name = prefix ? `${prefix} · ${humanise(key)}` : humanise(key)
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) return ruleRows(value as Record<string, unknown>, name)
    return [[name, Array.isArray(value) ? value.join(', ') : String(value)]]
  })
}

function PolicyContent({ policy, launcher }: { policy: PolicyView; launcher: LaunchState }) {
  return (
    <div className="policy-grid">
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
      <LiveTests launcher={launcher} />
      <section className="card section">
        <h2>Checks before any payout</h2>
        <table className="table">
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
                <td className="mono">{c.code}</td>
                <td>{c.applies}</td>
                <td>
                  <span className={`badge ${c.severity === 'HARD' ? 'badge--navy' : 'badge--amber'}`}>{c.severity}</span>
                </td>
                <td>{c.passes_when}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
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
