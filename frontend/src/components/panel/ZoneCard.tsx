/**
 * Triggered-zone card (SPEC §17.2, deck slide 6): status badge, "Zone 7 · 46 shops" with its ward,
 * a headline with the trailing 3-hour index and its hourly bars against the 50% floor, then the
 * exact panel rows from `GET /api/zones/{id}` (Alert / Sales / Cover / Paid / Total). A row that
 * changes (the 17:04 credit) flashes once; the badge fades in when the status changes. On a zone
 * that has not triggered, a muted "Now: 38% (live)" line gives the map's live window (B3).
 */
import type { ReactNode } from 'react'

import type { ZonePanel, ZoneSnapshot, ZoneStatusName } from '../../api/types'
import { useChangedKeys } from '../../state/motion'
import type { ZoneTrend } from './zoneTrend'

export type { ZoneTrend } from './zoneTrend'

export const STATUS_BADGES: Readonly<Record<ZoneStatusName, { text: string; tone: string }>> = Object.freeze({
  triggered: { text: 'Triggered', tone: 'red' },
  watch: { text: 'Watching', tone: 'amber' },
  slow_day: { text: 'Slow day', tone: 'grey' },
  normal: { text: 'Normal', tone: 'green' },
  no_data: { text: 'No data', tone: 'grey' },
})

/** Top of the sparkline scale (sales as % of expected). */
const SPARK_MAX_PCT = 100

export function zoneTitle(zoneId: string, shops: number): string {
  return `Zone ${zoneId.replace(/^Z/, '')} · ${shops} shops`
}

/** "14:00" → "14" for the sparkline's hour ticks. */
export function hourTick(label: string): string {
  return label.slice(0, 2)
}

/** What the card needs: the panel rows and the zone's identity (also built from the deck story). */
export type ZoneCardData = Pick<ZonePanel, 'rows'> & { zone: Pick<ZoneSnapshot, 'zone_id' | 'status' | 'shops' | 'ward' | 'name'> }

/**
 * Three hourly bars on a flat baseline: red below the trigger floor, grey-green above it. The floor is the
 * published rule (fs-08 13.2); while it is unknown the bars draw with no floor line and none turn red.
 */
function Spark({ hours, floorPct }: { hours: ZoneTrend['hours']; floorPct: number | null }) {
  return (
    <span className="spark">
      <span className="visually-hidden">Hourly sales vs expected: {hours.map((h) => `${h.label} ${h.pct}%`).join(', ')}</span>
      <span className="spark__plot" aria-hidden="true">
        {floorPct === null ? null : (
          <span className="spark__rule" style={{ bottom: `${(floorPct / SPARK_MAX_PCT) * 100}%` }}>
            <span className="spark__rule-label num">{floorPct}%</span>
          </span>
        )}
        {hours.map((h) => (
          <span
            key={h.label}
            className="spark__bar"
            data-low={floorPct !== null && h.pct < floorPct}
            title={`${h.label} · ${h.pct}% of expected`}
            style={{ height: `${Math.max(2, Math.min(SPARK_MAX_PCT, h.pct))}%` }}
          />
        ))}
      </span>
      <span className="spark__ticks num" aria-hidden="true">
        {hours.map((h) => (
          <span key={h.label}>{hourTick(h.label)}</span>
        ))}
      </span>
    </span>
  )
}

function Headline({ trend, live, floorPct }: { trend: ZoneTrend; live: number | null; floorPct: number | null }) {
  return (
    <div className="zone-card__hero">
      <strong className="zone-card__pct num">{trend.pct}%</strong>
      <span className="zone-card__hero-text">
        of expected sales
        {trend.window ? <span className="zone-card__window num">{trend.window}</span> : null}
        {live !== null ? <span className="zone-card__live num">Now: {live}% (live)</span> : null}
      </span>
      {trend.hours.length > 0 ? <Spark hours={trend.hours} floorPct={floorPct} /> : null}
    </div>
  )
}

/**
 * `action` sits at the end of the ward line of the card head: the H24 "What if..." button lives on the zone card
 * (fs-08 11) and shares that line, so it costs the panel no row even in presenter type.
 */
type Props = { panel: ZoneCardData; trend?: ZoneTrend | null; live?: number | null; floorPct?: number | null; action?: ReactNode }

export function ZoneCard({ panel, trend = null, live = null, floorPct = null, action = null }: Props) {
  const badge = STATUS_BADGES[panel.zone.status]
  const changed = useChangedKeys(Object.fromEntries(panel.rows.map((r) => [r.label, r.value])))
  return (
    <section className="card zone-card" aria-label={`Zone ${panel.zone.zone_id}`} data-status={panel.zone.status}>
      <header className="zone-card__head">
        <span key={panel.zone.status} className={`badge badge--${badge.tone} zone-card__badge`}>
          {badge.text}
        </span>
        <h2 className="zone-card__title">{zoneTitle(panel.zone.zone_id, panel.zone.shops)}</h2>
        <div className="zone-card__subrow">
          <p className="zone-card__sub">
            Ward {panel.zone.ward} · {panel.zone.name}
          </p>
          {action ? <span className="zone-card__action">{action}</span> : null}
        </div>
      </header>
      {trend ? <Headline trend={trend} live={live} floorPct={floorPct} /> : null}
      <dl className="zone-card__rows">
        {panel.rows.map((row) => (
          <div key={row.label} className={`zone-card__row ${changed.has(row.label) ? 'is-changed' : ''}`} data-row={row.label}>
            <dt>{row.label}</dt>
            <dd className="num">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
