/**
 * The audit chain as a table (SPEC §11): rows grouped under a sticky simulated-minute header,
 * money rows marked with a blue rule, and each hash matched to the next entry's "previous" hash
 * on hover (the link that makes the log tamper-evident). After a successful "Verify chain" a
 * green check lands on each row in turn. On a phone every entry becomes a small card.
 */
import { useState, type CSSProperties } from 'react'

import type { AuditEntry } from '../../api/types'
import { Icon } from '../common/Icon'
import { groupByMinute, isMoneyAction } from './auditGroups'

export const HASH_CHARS = 10
/** Checks after a verify arrive one row at a time for the first rows only. */
const STAGGER_ROWS = 24
const COLUMNS = 6

type RowProps = { entry: AuditEntry; index: number; hover: string | null; onHover: (hash: string | null) => void; verified: number }

function Row({ entry, index, hover, onHover, verified }: RowProps) {
  const style = { '--i': Math.min(index, STAGGER_ROWS) } as CSSProperties
  return (
    <tr className="audit-row" data-money={isMoneyAction(entry.action)} onMouseEnter={() => onHover(entry.hash)} onMouseLeave={() => onHover(null)}>
      <td className="num audit-row__seq" data-label="#">
        {verified > 0 ? (
          <span key={verified} className="audit-row__check" style={style} aria-hidden="true">
            <Icon name="check" size={12} />
          </span>
        ) : null}
        {entry.seq}
      </td>
      <td data-label="Actor">
        <span className="actor">{entry.actor}</span>
      </td>
      <td className="mono audit-row__action" data-label="Action">
        {entry.action}
      </td>
      <td data-label="Subject">
        {entry.subject_type} <span className="mono">{entry.subject_id}</span>
      </td>
      <td className="mono audit-hash" data-label="Hash" data-match={hover === entry.hash} title={entry.hash}>
        {entry.hash.slice(0, HASH_CHARS)}
      </td>
      <td className="mono muted audit-hash" data-label="Previous" data-match={hover === entry.prev_hash} title={entry.prev_hash}>
        {entry.prev_hash.slice(0, HASH_CHARS)}
      </td>
    </tr>
  )
}

/** `entries` newest first; `verified` counts successful verifies (0: none yet). */
export function AuditTable({ entries, verified }: { entries: readonly AuditEntry[]; verified: number }) {
  const [hover, setHover] = useState<string | null>(null)
  const groups = groupByMinute(entries)
  const indexOf = new Map(entries.map((e, i) => [e.seq, i]))
  return (
    <table className="table audit-table" data-verified={verified > 0}>
      <thead>
        <tr>
          <th className="num">#</th>
          <th>Actor</th>
          <th>Action</th>
          <th>Subject</th>
          <th>Hash</th>
          <th>Previous</th>
        </tr>
      </thead>
      {groups.map((group) => (
        <tbody key={group.key}>
          <tr className="audit-group">
            <th colSpan={COLUMNS} scope="rowgroup">
              {group.label}
            </th>
          </tr>
          {group.items.map((entry) => (
            <Row key={entry.seq} entry={entry} index={indexOf.get(entry.seq) ?? 0} hover={hover} onHover={setHover} verified={verified} />
          ))}
        </tbody>
      ))}
    </table>
  )
}
