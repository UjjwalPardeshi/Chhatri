/** Policy checks for a decision (SPEC §9.2): pass / fail / unsure (soft) / waived, with the numbers. */
import type { Check } from '../../api/types'
import { Icon } from '../common/Icon'
import { CHECK_STATUS } from './labels'

export function Checks({ checks }: { checks: readonly Check[] }) {
  return (
    <table className="table checks">
      <thead>
        <tr>
          <th>Check</th>
          <th>Result</th>
          <th>Observed</th>
          <th>Required</th>
        </tr>
      </thead>
      <tbody>
        {checks.map((check) => {
          const status = CHECK_STATUS[check.status]
          return (
            <tr key={check.code} data-status={check.status}>
              <td>
                <span className="checks__label">{check.label_en}</span>
                <span className="checks__code mono">
                  {check.code} · {check.severity}
                </span>
              </td>
              <td>
                <span className={`check-pill check-pill--${status.tone}`}>
                  <Icon name={status.icon} size={13} />
                  {status.label}
                  {check.severity === 'SOFT' && check.status !== 'PASS' ? ' (soft)' : ''}
                </span>
              </td>
              <td>{check.observed ?? '—'}</td>
              <td className="muted">{check.required ?? '—'}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
