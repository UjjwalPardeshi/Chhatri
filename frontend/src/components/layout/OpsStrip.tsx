/**
 * The H8 ops strip (fs-08 10, flag h8_ops_strip): a slim band under the control bar on /live and /claims with five
 * cells, each a button. Open cases opens /claims, Next due opens that case, and the other three open a popover with
 * the counts behind the figure. Numbers count up over 500 ms and a cell flashes when its value changes (reduced motion
 * keeps the colour change only). A failed request says "Ops numbers unavailable" with a Retry button: it never shows
 * stale numbers without saying so. `OpsStripView` is the pure view; `OpsStrip` reads the shared ops state.
 */
import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { useLocation, useNavigate } from 'react-router'

import type { OpsSummary } from '../../api/opsWhatIf'
import { formatInr } from '../../lib/money'
import { useLive } from '../../state/live'
import { COUNT_UP_MS, useChangedKeys, useCountUp } from '../../state/motion'
import { useOps } from '../../state/ops'
import { enginePopover, engineLine, holidayLines, holidayPopover, kindsLine, nextDue, paidSub, plural, zoneRows } from './opsStripModel'

/** The routes that carry the strip (fs-08 10.1). */
export const OPS_STRIP_PATHS: readonly string[] = ['/live', '/claims']

type CellKey = 'open' | 'due' | 'engine' | 'paid' | 'holiday'
type PopoverRow = { label: string; value: string | number }

function Count({ value, format = String }: { value: number; format?: (n: number) => string }) {
  return <>{format(useCountUp(value, COUNT_UP_MS))}</>
}

type CellProps = {
  id: CellKey
  label: string
  changed: boolean
  tone?: 'warn' | 'overdue'
  value: ReactNode
  sub?: string | null
  onClick?: () => void
  expanded?: boolean
  disabled?: boolean
}

function Cell({ id, label, changed, tone, value, sub, onClick, expanded, disabled }: CellProps) {
  return (
    <button type="button" className="ops-cell" data-cell={id} data-changed={changed ? 'true' : undefined} data-tone={tone} aria-expanded={expanded} onClick={onClick} disabled={disabled}>
      <span className="ops-cell__label">{label}</span>
      <span className="ops-cell__value">{value}</span>
      {sub ? <span className="ops-cell__sub">{sub}</span> : null}
    </button>
  )
}

function Popover({ title, rows, onClose }: { title: string; rows: readonly PopoverRow[]; onClose: () => void }) {
  return (
    <dialog className="ops-pop" open aria-label={title}>
      <div className="ops-pop__head">
        <strong>{title}</strong>
        <button type="button" className="ops-pop__close" aria-label={`Close ${title}`} onClick={onClose}>
          ×
        </button>
      </div>
      <dl className="ops-pop__rows">
        {rows.map((row) => (
          <div key={row.label} className="ops-pop__row">
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </dialog>
  )
}

function popoverFor(key: CellKey, summary: OpsSummary): { title: string; rows: PopoverRow[] } | null {
  if (key === 'engine') return { title: 'Who decided today', rows: enginePopover(summary.claims_today) }
  if (key === 'paid') {
    const rows = zoneRows(summary).map((r) => ({ label: `${r.zone} · ${plural(r.count, 'shop')}`, value: r.label }))
    return { title: 'Paid today by zone', rows: rows.length > 0 ? rows : [{ label: 'Nothing credited yet', value: formatInr(0) }] }
  }
  if (key === 'holiday' && summary.holiday_requests_today) return { title: 'Holiday requests today', rows: holidayPopover(summary.holiday_requests_today) }
  return null
}

function usePopover(): { open: CellKey | null; toggle: (key: CellKey) => void; close: () => void; ref: RefObject<HTMLDivElement | null> } {
  const [open, setOpen] = useState<CellKey | null>(null)
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (open === null) return undefined
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(null)
    }
    const onDown = (event: MouseEvent) => {
      if (ref.current && event.target instanceof Node && !ref.current.contains(event.target)) setOpen(null)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDown)
    }
  }, [open])
  return { open, toggle: (key) => setOpen((current) => (current === key ? null : key)), close: () => setOpen(null), ref }
}

export type OpsStripViewProps = {
  summary: OpsSummary | null
  error: boolean
  loading: boolean
  nowIso: string
  onRetry: () => void
  onNavigate: (to: string) => void
}

export function OpsStripView({ summary, error, loading, nowIso, onRetry, onNavigate }: OpsStripViewProps) {
  const pop = usePopover()
  const { ref: stripRef } = pop
  const changed = useChangedKeys(
    summary
      ? { open: String(summary.open_cases), due: summary.next_due_case?.id ?? '', engine: engineLine(summary.claims_today), paid: `${summary.payouts_today.credited_paise}|${summary.payouts_today.pending_count}`, holiday: JSON.stringify(summary.holiday_requests_today) }
      : {},
  )
  if (error || (!summary && !loading)) {
    return (
      <section className="ops-strip ops-strip--error" aria-label="Operations today">
        <span role="alert">Ops numbers unavailable</span>
        <button type="button" className="btn" onClick={onRetry}>
          Retry
        </button>
      </section>
    )
  }
  if (!summary) {
    return (
      <section className="ops-strip" aria-label="Operations today" aria-busy="true">
        <span className="ops-strip__note">Loading ops numbers…</span>
      </section>
    )
  }
  const due = nextDue(summary, nowIso)
  const engine = summary.claims_today
  const paid = summary.payouts_today
  const holiday = summary.holiday_requests_today
  const holidayText = holiday ? holidayLines(holiday) : null
  const popover = pop.open ? popoverFor(pop.open, summary) : null
  const cell = (key: CellKey) => ({ id: key, changed: changed.has(key) })
  const expanded = (key: CellKey) => pop.open === key
  return (
    <section className="ops-strip" aria-label="Operations today" ref={stripRef}>
      <Cell {...cell('open')} label="Open cases" value={<Count value={summary.open_cases} />} sub={kindsLine(summary.cases_by_kind)} onClick={() => onNavigate('/claims')} />
      <Cell
        {...cell('due')}
        label="Next due"
        value={due ? due.text : 'Nothing due'}
        sub={due?.toneWord}
        tone={due?.tone === 'ok' ? undefined : due?.tone}
        disabled={!due}
        onClick={() => due && onNavigate(`/claims?case=${due.caseId}`)}
      />
      <Cell {...cell('engine')} label="Decided by the engine" value={engineLine(engine)} onClick={() => pop.toggle('engine')} expanded={expanded('engine')} />
      <Cell
        {...cell('paid')}
        label="Paid today"
        value={
          <>
            <Count value={paid.credited_paise} format={formatInr} /> · {plural(paid.credited_count, 'shop')}
          </>
        }
        sub={paidSub(paid.pending_count)}
        tone={paid.pending_count > 0 ? 'warn' : undefined}
        onClick={() => pop.toggle('paid')}
        expanded={expanded('paid')}
      />
      {holidayText ? <Cell {...cell('holiday')} label="Holiday requests" value={holidayText.main} sub={holidayText.others} onClick={() => pop.toggle('holiday')} expanded={expanded('holiday')} /> : null}
      {popover ? <Popover title={popover.title} rows={popover.rows} onClose={pop.close} /> : null}
    </section>
  )
}

/** The strip on /live and /claims; the flag and the page check are the caller's (AppShell). */
export function OpsStrip() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { snapshot } = useLive()
  const { summary, error, loading, reload } = useOps()
  if (!OPS_STRIP_PATHS.includes(pathname)) return null
  return <OpsStripView summary={summary} error={error !== null} loading={loading} nowIso={snapshot?.clock.now ?? summary?.as_of ?? ''} onRetry={reload} onNavigate={(to) => void navigate(to)} />
}
