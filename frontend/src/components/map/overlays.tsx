/** Map overlays (deck slide 6): clock chip, north arrow, legend, offline note, rain hatch pattern. */
import type { ClockState } from '../../api/types'
import { COLOUR_STOPS, LEGEND_RULE, legendGradient } from '../../lib/colour'
import { Icon } from '../common/Icon'
import { splitClockLabel } from '../layout/ControlBar'
import type { TileFailure } from './layers'

export function MapChip({ clock, alertActive }: { clock: ClockState; alertActive: boolean }) {
  const { main, tail } = splitClockLabel(clock.label)
  return (
    <div className="map-chip" data-alert={alertActive}>
      <span className="map-chip__dot" />
      <strong>{main}</strong>
      {tail ? <span className="muted"> · {tail}</span> : null}
    </div>
  )
}

export function NorthArrow() {
  return (
    <div className="north-arrow" aria-label="North">
      <span>N</span>
      <Icon name="north" size={16} />
    </div>
  )
}

export function Legend() {
  const first = COLOUR_STOPS[0].pct
  const middle = COLOUR_STOPS[Math.floor(COLOUR_STOPS.length / 2)].pct
  const last = COLOUR_STOPS[COLOUR_STOPS.length - 1].pct
  const [rulePays, ruleRest] = LEGEND_RULE.split(' for ')
  return (
    <div className="map-legend" aria-label="Legend: sales vs expected">
      <div className="map-legend__scale">
        <span className="map-legend__title">Sales vs expected</span>
        <span className="map-legend__bar" style={{ background: legendGradient() }} />
        <span className="map-legend__ticks">
          <span>{first}%</span>
          <span>{middle}%</span>
          <span>{last}%+</span>
        </span>
      </div>
      <div className="map-legend__rule" title={LEGEND_RULE}>
        <strong>{rulePays}</strong>
        <span>for {ruleRest}</span>
      </div>
    </div>
  )
}

export function offlineText(reason: TileFailure): string {
  return reason === 'watermark' ? 'Ward basemap · no CARTO tile key' : 'Basemap offline · wards shown'
}

export function OfflineNote({ reason }: { reason: TileFailure }) {
  return (
    <div className="map-offline" data-reason={reason}>
      {offlineText(reason)}
    </div>
  )
}

/** Hatch pattern referenced by `.rain-band { fill: url(#rain-hatch) }`; animated like falling rain. */
export function RainPatternDefs() {
  return (
    <svg className="rain-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <pattern id="rain-hatch" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(28)">
          <rect width="9" height="9" fill="rgba(56,163,232,0.07)" />
          <line x1="4" y1="0" x2="4" y2="9" stroke="rgba(11,99,201,0.42)" strokeWidth="1.2" strokeDasharray="5 4">
            <animate attributeName="stroke-dashoffset" values="9;0" dur="0.8s" repeatCount="indefinite" />
          </line>
        </pattern>
      </defs>
    </svg>
  )
}
