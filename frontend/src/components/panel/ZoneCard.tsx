/**
 * Triggered-zone card (SPEC §17.2, deck slide 6): status badge, "Zone 7 · 46 shops", a headline
 * with the trailing 3-hour index and its hourly bars against the 50% floor, then the exact panel
 * rows from `GET /api/zones/{id}` (Alert / Sales / Cover / Paid / Total). A row that changes (the
 * 17:04 credit) flashes once; the badge fades in when the status changes.
 */
import type { ZonePanel, ZoneSnapshot, ZoneStatusName } from '../../api/types'
import { indexColour, INDEX_FLOOR_PCT } from '../../lib/colour'
import { useChangedKeys } from '../../state/motion'

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

/** What the card needs: the panel rows and the zone's identity (also built from the deck story). */
export type ZoneCardData = Pick<ZonePanel, 'rows'> & { zone: Pick<ZoneSnapshot, 'zone_id' | 'status' | 'shops' | 'ward' | 'name'> }

/** The headline: the window index and the hours that make it up. */
export type ZoneTrend = { pct: number; hours: readonly { label: string; pct: number }[] }

function Spark({ hours }: { hours: ZoneTrend['hours'] }) {
  return (
    <span className="spark" aria-hidden="true">
      <span className="spark__rule" style={{ bottom: `${(INDEX_FLOOR_PCT / SPARK_MAX_PCT) * 100}%` }}>
        <span className="spark__rule-label num">{INDEX_FLOOR_PCT}%</span>
      </span>
      {hours.map((h) => (
        <span key={h.label} className="spark__bar" title={`${h.label} · ${h.pct}%`} style={{ height: `${Math.min(SPARK_MAX_PCT, h.pct)}%`, background: indexColour(h.pct) }} />
      ))}
    </span>
  )
}

function Headline({ trend }: { trend: ZoneTrend }) {
  const first = trend.hours[0]?.label
  const last = trend.hours.at(-1)?.label
  return (
    <div className="zone-card__hero">
      <strong className="zone-card__pct num">{trend.pct}%</strong>
      <span className="zone-card__hero-text">
        of expected sales
        {first && last ? (
          <span className="muted num">
            {' '}
            · {first} to {last}
          </span>
        ) : null}
      </span>
      {trend.hours.length > 0 ? <Spark hours={trend.hours} /> : null}
    </div>
  )
}

export function ZoneCard({ panel, trend = null }: { panel: ZoneCardData; trend?: ZoneTrend | null }) {
  const badge = STATUS_BADGES[panel.zone.status]
  const changed = useChangedKeys(Object.fromEntries(panel.rows.map((r) => [r.label, r.value])))
  return (
    <section className="card zone-card" aria-label={`Zone ${panel.zone.zone_id}`} data-status={panel.zone.status}>
      <header className="zone-card__head">
        <span key={panel.zone.status} className={`badge badge--${badge.tone} zone-card__badge`}>
          {badge.text}
        </span>
        <h2 className="zone-card__title">{zoneTitle(panel.zone.zone_id, panel.zone.shops)}</h2>
      </header>
      <p className="zone-card__sub muted">
        Ward {panel.zone.ward} · {panel.zone.name}
      </p>
      {trend ? <Headline trend={trend} /> : null}
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
