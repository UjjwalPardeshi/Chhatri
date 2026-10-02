/**
 * Policy checks for a decision (SPEC §9.2): what blocked the money first (fail, unsure, waived,
 * then pass), failed rows tinted, the check code in quiet mono under its label. On a phone each
 * row becomes a small card (CSS).
 */
import type { Check, Source } from '../../api/types'
import { Icon } from '../common/Icon'
import { CHECK_STATUS } from './labels'
import { sourceChipText } from './receiptParts'
import { sortChecks } from './whyHuman'

type SourcesProps = {
  /** The sources of each check from the receipt (H13), by check code. Absent until the receipt is known. */
  sources?: Readonly<Record<string, readonly Source[]>>
  /** True while the receipt loads: the column shows a grey bar. */
  sourcesLoading?: boolean
}

function SourceCell({ list }: { list: readonly Source[] | undefined }) {
  if (!list || list.length === 0) return <span className="muted">—</span>
  return (
    <ul className="source-chips">
      {list.map((s) => (
        <li key={s.ref} className="source-chip" data-origin={s.origin} title={s.clause ? `${s.kind} · clause ${s.clause}` : s.kind}>
          {sourceChipText(s)}
        </li>
      ))}
    </ul>
  )
}

export function Checks({ checks, sources, sourcesLoading = false }: { checks: readonly Check[] } & SourcesProps) {
  const showSources = sources !== undefined || sourcesLoading
  return (
    <table className="table checks">
      <thead>
        <tr>
          <th>Check</th>
          <th>Result</th>
          <th>Observed</th>
          <th>Required</th>
          {showSources ? <th>Source</th> : null}
        </tr>
      </thead>
      <tbody>
        {sortChecks(checks).map((check) => {
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
              <td data-label="Observed">{check.observed ?? '—'}</td>
              <td className="muted" data-label="Required">
                {check.required ?? '—'}
              </td>
              {showSources ? (
                <td data-label="Source">{sourcesLoading ? <span className="skeleton" aria-label="Loading sources" /> : <SourceCell list={sources?.[check.code]} />}</td>
              ) : null}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
