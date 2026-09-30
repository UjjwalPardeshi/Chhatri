/**
 * Humans in control (deck slide 8, SPEC §9.4 authority table, §13.6 three live tests), with the
 * waiting-period rule and a way into the audit log that records every decision (SPEC §11).
 */
import { Link } from 'react-router'

import { AUTHORITY } from '../../content/deck'
import { Icon } from '../common/Icon'
import type { LaunchState } from '../../state/useLaunch'
import { LiveTests } from './LiveTests'
import { RevealSection } from './Reveal'

export function authorityTone(cell: string): string {
  if (cell.startsWith('Never')) return 'cell--never'
  if (cell.startsWith('Pays')) return 'cell--pays'
  return ''
}

export function AuthorityTable() {
  return (
    <table className="table authority">
      <thead>
        <tr>
          <th>Case</th>
          <th>Chhatri alone</th>
          <th>Goes to a human</th>
        </tr>
      </thead>
      <tbody>
        {AUTHORITY.map((row) => (
          <tr key={row.case}>
            <td>{row.case}</td>
            <td className={authorityTone(row.alone)}>{row.alone}</td>
            <td>{row.human}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function Humans({ launcher }: { launcher: LaunchState }) {
  return (
    <RevealSection label="Humans in control" id="ov-humans" className="ov-humans" tone="white">
      <h2 className="ov-h2">Automatic when the data is clear, human when it isn’t.</h2>
      <div className="ov-humans__grid">
        <div>
          <p className="ov-label">Payout authority · starting rules for the pilot</p>
          <AuthorityTable />
          <p className="ov-note">
            New cover starts only after a <strong>waiting period</strong>, so nobody can buy it once a storm is forecast.
          </p>
          <Link className="audit-teaser" to="/audit">
            <span className="audit-teaser__icon" aria-hidden="true">
              <Icon name="shield" size={18} />
            </span>
            <span>
              <strong>Every payout is logged</strong>
              <span className="audit-teaser__text">Each decision, credit and instalment pause is written to a hash-chained audit log that anyone can verify.</span>
            </span>
            <Icon name="arrow" size={16} />
          </Link>
        </div>
        <LiveTests launcher={launcher} />
      </div>
    </RevealSection>
  )
}
