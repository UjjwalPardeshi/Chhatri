/**
 * Map overlays (deck slide 6): the alert status chip, north arrow, legend, the offline note and
 * the SVG patterns for the rain band hatch and the no-shops stipple. The header owns the clock
 * (SPEC §20), so the map shows what the alert is doing instead. Overlays carry `data-obstacle` so
 * zone labels are placed around them.
 */
import type { ClockState, ZoneSnapshot } from '../../api/types'
import { COLOUR_STOPS, legendGradient, legendRule } from '../../lib/colour'
import type { TriggerRule } from '../../lib/rules'
import { hhmm } from '../../lib/time'
import { Icon } from '../common/Icon'
import type { TileFailure } from './basemap'

const LEVEL_WORDS: Readonly<Record<string, string>> = Object.freeze({ RED: 'Red', ORANGE: 'Orange', YELLOW: 'Yellow' })
const PCT = 100

export type AlertStatus = { tone: 'red' | 'amber'; text: string; live: boolean }

function zonesWord(n: number): string {
  return n === 1 ? '1 zone' : `${n} zones`
}

/**
 * The map's status line: "Red alert from 14:00 · 3 zones" before the alert window,
 * "Red alert active · 3 zones on watch" during it, "Red alert · 3 zones triggered" once paid out.
 * Null when no zone has an alert.
 */
export function alertStatus(zones: readonly ZoneSnapshot[], clock: Pick<ClockState, 'now'>): AlertStatus | null {
  const alerted = zones.filter((z) => z.alert !== null)
  const first = alerted[0]?.alert
  if (!first) return null
  const level = LEVEL_WORDS[first.level] ?? first.level
  const tone = first.level === 'RED' ? 'red' : 'amber'
  const now = Date.parse(clock.now)
  const triggered = zones.filter((z) => z.status === 'triggered').length
  if (triggered > 0) return { tone, text: `${level} alert · ${zonesWord(triggered)} triggered`, live: true }
  if (now < Date.parse(first.valid_from)) return { tone, text: `${level} alert from ${hhmm(first.valid_from)} · ${zonesWord(alerted.length)}`, live: false }
  if (now >= Date.parse(first.valid_to)) return null
  return { tone, text: `${level} alert active · ${zonesWord(alerted.length)} on watch`, live: true }
}

export function StatusChip({ status }: { status: AlertStatus | null }) {
  if (!status) return null
  return (
    <div className="map-status" data-tone={status.tone} data-live={status.live} data-obstacle>
      <span className="map-status__dot" />
      {status.text}
    </div>
  )
}

export function NorthArrow() {
  return (
    <div className="north-arrow" aria-label="North" data-obstacle>
      <span>N</span>
      <Icon name="north" size={16} />
    </div>
  )
}

/** Where a sales-vs-expected value sits on the legend bar (% of its width). */
export function legendPct(value: number): number {
  const first = COLOUR_STOPS[0].pct
  const last = COLOUR_STOPS[COLOUR_STOPS.length - 1].pct
  return ((Math.min(last, Math.max(first, value)) - first) / (last - first)) * PCT
}

type LegendProps = {
  patterns: string
  /** The published trigger rule; null while it is unknown, and the legend then draws the ramp with no floor and no rule line. */
  rule: TriggerRule | null
}

/**
 * The deck legend (slide 6, SPEC §20 "Pays below 50% for 3 h, with alert"): the colour ramp with
 * the payout floor marked on it, the live-window caption (B3: map values are the live 3-hour
 * window), and swatches for the rain band hatch and land without shops. The floor and the rule
 * line come from the published rules (fs-08 13.2), never from a constant.
 */
export function Legend({ patterns, rule }: LegendProps) {
  const first = COLOUR_STOPS[0].pct
  const middle = COLOUR_STOPS[Math.floor(COLOUR_STOPS.length / 2)].pct
  const last = COLOUR_STOPS[COLOUR_STOPS.length - 1].pct
  const text = rule ? legendRule(rule) : null
  const [rulePays, ruleRest] = text ? text.split(' for ') : ['', '']
  const ticks = [
    { pct: legendPct(first), text: `${first}%`, floor: false },
    ...(rule ? [{ pct: legendPct(rule.floorPct), text: `${rule.floorPct}%`, floor: true }] : []),
    { pct: legendPct(middle), text: `${middle}%`, floor: false },
    { pct: legendPct(last), text: `${last}%+`, floor: false },
  ]
  return (
    <div className="map-legend" aria-label="Legend: sales vs expected" data-obstacle>
      <p className="map-legend__title">
        Sales vs expected <span className="map-legend__caption">live 3-hour window</span>
      </p>
      <span className="map-legend__bar" style={{ background: legendGradient() }}>
        {rule ? <span className="map-legend__floor" style={{ left: `${legendPct(rule.floorPct)}%` }} /> : null}
      </span>
      <span className="map-legend__ticks num">
        {ticks.map((t) => (
          <span key={t.text} className={t.floor ? 'map-legend__tick map-legend__tick--floor' : 'map-legend__tick'} style={{ left: `${t.pct}%` }}>
            {t.text}
          </span>
        ))}
      </span>
      {text ? (
        <p className="map-legend__rule" title={text}>
          <strong>{rulePays}</strong> for {ruleRest}
        </p>
      ) : null}
      <p className="map-legend__keys">
        <span className="map-legend__key">
          <svg className="map-legend__swatch" viewBox="0 0 14 10" aria-hidden="true" focusable="false">
            <rect width="14" height="10" rx="2" fill={`url(#${patterns}-hatch)`} className="map-legend__swatch-rain" />
          </svg>
          Heavy rain
        </span>
        <span className="map-legend__key">
          <svg className="map-legend__swatch" viewBox="0 0 14 10" aria-hidden="true" focusable="false">
            <rect width="14" height="10" rx="2" fill={`url(#${patterns}-stipple)`} className="map-legend__swatch-land" />
          </svg>
          No shops
        </span>
      </p>
    </div>
  )
}

/**
 * The basemap note. Without a tile key the drawn ward basemap is the intended design, so it says
 * nothing (the reason stays in the map's title); only a real outage is announced.
 */
export function offlineText(reason: TileFailure): string | null {
  return reason === 'watermark' ? null : 'Basemap offline · wards shown'
}

export function basemapTitle(reason: TileFailure | null): string {
  if (reason === null) return 'Basemap: CARTO Positron'
  return reason === 'watermark' ? 'Ward basemap (no CARTO tile key configured)' : 'Ward basemap (tiles unavailable)'
}

export function OfflineNote({ reason }: { reason: TileFailure }) {
  const text = offlineText(reason)
  if (!text) return null
  return (
    <div className="map-offline" data-reason={reason} data-obstacle>
      {text}
    </div>
  )
}

/** Rain band hatch (SPEC §20 "rain band overlay"): 45° accent lines, 2 px wide every 7 px. */
export const RAIN_HATCH = Object.freeze({ spacing: 7, width: 2, colour: '#38a3e8', opacity: 0.45 })
/** Land without shops: a light grey stipple, so ward lines and the coast still read there. */
export const LAND_STIPPLE = Object.freeze({ cell: 6, dot: 0.9, land: '#eef1f5', ink: 'rgb(15 26 51 / 12%)' })

/**
 * SVG patterns shared by a map and its legend (`${prefix}-hatch`, `${prefix}-stipple`). Pattern
 * ids are document-wide, so the Leaflet layers and the legend swatches can both reference them.
 */
export function MapPatternDefs({ prefix }: { prefix: string }) {
  const half = RAIN_HATCH.spacing / 2
  const quarter = LAND_STIPPLE.cell / 4
  return (
    <svg className="map-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <pattern id={`${prefix}-hatch`} width={RAIN_HATCH.spacing} height={RAIN_HATCH.spacing} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1={half} y1="0" x2={half} y2={RAIN_HATCH.spacing} stroke={RAIN_HATCH.colour} strokeWidth={RAIN_HATCH.width} strokeOpacity={RAIN_HATCH.opacity} />
        </pattern>
        <pattern id={`${prefix}-stipple`} width={LAND_STIPPLE.cell} height={LAND_STIPPLE.cell} patternUnits="userSpaceOnUse">
          <rect width={LAND_STIPPLE.cell} height={LAND_STIPPLE.cell} fill={LAND_STIPPLE.land} />
          <circle cx={quarter} cy={quarter} r={LAND_STIPPLE.dot} fill={LAND_STIPPLE.ink} />
          <circle cx={3 * quarter} cy={3 * quarter} r={LAND_STIPPLE.dot} fill={LAND_STIPPLE.ink} />
        </pattern>
      </defs>
    </svg>
  )
}
