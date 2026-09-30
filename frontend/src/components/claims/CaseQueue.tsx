/** Officer queue (SPEC §20 "Claims"): id, kind, merchant, age and SLA countdown on simulated time. */
import type { Case } from '../../api/types'
import { ageLabel, slaState } from '../../lib/time'
import { CASE_KIND_LABELS, CASE_STATUS_TONES } from './labels'

type Props = { cases: readonly Case[]; selected: string | null; now: string; onSelect: (id: string) => void }

export function CaseQueue({ cases, selected, now, onSelect }: Props) {
  if (cases.length === 0) {
    return <p className="queue__empty muted">No cases. Doubtful claims and disputes land here.</p>
  }
  return (
    <ul className="queue" aria-label="Cases">
      {cases.map((c) => {
        const sla = slaState(c.due_by, now)
        return (
          <li key={c.id}>
            <button type="button" className={`queue__item ${c.id === selected ? 'is-selected' : ''}`} aria-current={c.id === selected} onClick={() => onSelect(c.id)}>
              <span className="queue__top">
                <strong className="queue__id">{c.id}</strong>
                <span className={`badge badge--${CASE_STATUS_TONES[c.status]}`}>{c.status}</span>
              </span>
              <span className="queue__kind">{CASE_KIND_LABELS[c.kind]}</span>
              <span className="queue__merchant">{c.merchant_name}</span>
              <span className="queue__meta num">
                <span>opened {ageLabel(c.opened_at, now)}</span>
                {c.status === 'OPEN' ? <span className={`sla sla--${sla.tone}`}>SLA {sla.label}</span> : null}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
