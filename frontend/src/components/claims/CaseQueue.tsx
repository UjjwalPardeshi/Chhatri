/**
 * Officer queue (SPEC §20 "Claims"): id, kind, merchant, age and SLA countdown on simulated time.
 * Open cases come first; resolved ones stay listed but quiet. A status change re-keys its badge so
 * it settles in once instead of switching silently.
 */
import type { Case } from '../../api/types'
import { ageLabel, slaState } from '../../lib/time'
import { Icon } from '../common/Icon'
import { CASE_KIND_LABELS, CASE_STATUS_TONES } from './labels'

type Props = { cases: readonly Case[]; selected: string | null; now: string; onSelect: (id: string) => void }

function EmptyQueue() {
  return (
    <div className="queue__empty">
      <span className="queue__empty-icon" aria-hidden="true">
        <Icon name="shield" size={18} />
      </span>
      <p>
        <strong>No cases</strong>
        <span className="muted">Doubtful claims and disputes land here.</span>
      </p>
    </div>
  )
}

function QueueItem({ item, selected, now, onSelect }: { item: Case; selected: boolean; now: string; onSelect: (id: string) => void }) {
  const sla = slaState(item.due_by, now)
  const open = item.status === 'OPEN'
  return (
    <button type="button" className={`queue__item ${selected ? 'is-selected' : ''} ${open ? '' : 'is-resolved'}`} aria-current={selected} onClick={() => onSelect(item.id)}>
      <span className="queue__top">
        <strong className="queue__id">{item.id}</strong>
        <span key={item.status} className={`badge badge--${CASE_STATUS_TONES[item.status]} queue__badge`}>
          {item.status}
        </span>
      </span>
      <span className="queue__kind">{CASE_KIND_LABELS[item.kind]}</span>
      <span className="queue__merchant">{item.merchant_name}</span>
      <span className="queue__meta num">
        <span>opened {ageLabel(item.opened_at, now)}</span>
        {open ? <span className={`sla sla--${sla.tone}`}>SLA {sla.label}</span> : null}
      </span>
    </button>
  )
}

export function CaseQueue({ cases, selected, now, onSelect }: Props) {
  if (cases.length === 0) return <EmptyQueue />
  return (
    <ul className="queue" aria-label="Cases">
      {cases.map((c) => (
        <li key={c.id}>
          <QueueItem item={c} selected={c.id === selected} now={now} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  )
}
