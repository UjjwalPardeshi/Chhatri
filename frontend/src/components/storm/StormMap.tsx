/**
 * The storm at 17:05 as a static, non-interactive map (deck slide 6; SPEC §17.2 golden labels;
 * B3 hex values): sea and land built from the ward polygons, hexes on the deck's colour scale, the
 * rain band under the hexes with a dashed edge, triggered zones outlined in red, dark zone labels
 * with leader lines, the Z9 callout, Anil's pin card and the legend in the corner. Drawn from
 * `content/stormMap.json` (see stormMapData.ts), so it needs no tiles, no Leaflet and no network.
 */
import type { CSSProperties } from 'react'

import stormMap from '../../content/stormMap.json'
import { indexColour } from '../../lib/colour'
import { Icon } from '../common/Icon'
import { Legend, NorthArrow } from '../map/overlays'
import type { Point, StormLabel, StormMapData } from './stormMapData'

export const STORM_MAP: StormMapData = stormMap as unknown as StormMapData

/** Label offsets from their zone anchor, in SVG units (deck slide 6: Z3 left, Z12 below, Z7 right). */
export const LABEL_OFFSETS: Readonly<Record<string, Point>> = Object.freeze({
  Z3: [-118, 26],
  Z7: [128, 34],
  Z12: [96, 58],
  Z9: [58, -70],
})
/** Where the water names sit in the frame (SVG units). */
const WATER: readonly { name: string; at: Point }[] = [
  { name: 'Arabian Sea', at: [96, 548] },
  { name: 'Harbour', at: [705, 470] },
]
const RAIN_CAPTION = 'Heavy rain band · since 14:00'

type Positioned = CSSProperties & { '--x': string; '--y': string }

function at(point: Point, data: StormMapData): Positioned {
  return { '--x': `${(point[0] / data.w) * 100}%`, '--y': `${(point[1] / data.h) * 100}%` }
}

function offset(label: StormLabel): Point {
  const [dx, dy] = LABEL_OFFSETS[label.id] ?? [0, 0]
  return [label.at[0] + dx, label.at[1] + dy]
}

function Paths({ data }: { data: StormMapData }) {
  const rain = new Set(data.rain)
  const triggered = new Set(data.triggered)
  return (
    <>
      <rect className="storm-map__sea" width={data.w} height={data.h} />
      <g className="storm-map__shallows">
        {data.land.map((z) => (
          <path key={z.id} d={z.d} />
        ))}
      </g>
      <g className="storm-map__coast">
        {data.land.map((z) => (
          <path key={z.id} d={z.d} />
        ))}
      </g>
      <g className="storm-map__land">
        {data.land.map((z) => (
          <path key={z.id} d={z.d} />
        ))}
      </g>
      <g className="storm-map__rain-fill">{data.land.filter((z) => rain.has(z.id)).map((z) => <path key={z.id} d={z.d} />)}</g>
      <g className="storm-map__hexes">
        {data.hexes.map((h, i) => (
          <path key={i} d={h.d} fill={indexColour(h.v)} />
        ))}
      </g>
      <g className="storm-map__wards">
        {data.land.map((z) => (
          <path key={z.id} d={z.d} />
        ))}
      </g>
      <g className="storm-map__rain-edge">{data.land.filter((z) => rain.has(z.id)).map((z) => <path key={z.id} d={z.d} />)}</g>
      <g className="storm-map__triggered">{data.land.filter((z) => triggered.has(z.id)).map((z) => <path key={z.id} d={z.d} />)}</g>
      <g className="storm-map__leaders">
        {data.labels.map((l) => {
          const [x, y] = offset(l)
          return (
            <g key={l.id}>
              <line x1={l.at[0]} y1={l.at[1]} x2={x} y2={y} />
              <circle cx={l.at[0]} cy={l.at[1]} r={4} />
            </g>
          )
        })}
      </g>
    </>
  )
}

function Labels({ data }: { data: StormMapData }) {
  return (
    <>
      {data.labels.map((l) =>
        l.status === 'slow_day' ? (
          <div key={l.id} className="storm-label storm-label--slow" style={at(offset(l), data)}>
            <strong>{l.text}</strong>
            <span>Slow day, no alert: no payout</span>
          </div>
        ) : (
          <div key={l.id} className="storm-label" style={at(offset(l), data)}>
            {l.text}
          </div>
        ),
      )}
      {data.pin ? (
        <div className="storm-pin" style={at(data.pin.at, data)}>
          <span className="storm-pin__dot" />
          <div className="storm-pin__card">
            <strong>{data.pin.name}</strong>
            <span>{data.pin.caption}</span>
          </div>
        </div>
      ) : null}
      {data.rainTop ? (
        <span className="rain-pill storm-map__rain-pill" style={at(data.rainTop, data)}>
          <Icon name="drop" size={12} />
          {RAIN_CAPTION}
        </span>
      ) : null}
      {WATER.map((w) => (
        <span key={w.name} className="storm-map__water" style={at(w.at, data)}>
          {w.name}
        </span>
      ))}
    </>
  )
}

export function StormMap({ data = STORM_MAP, when }: { data?: StormMapData; when: string }) {
  return (
    <figure className="storm-map" aria-label={`Storm replay map at ${when}`}>
      <svg className="storm-map__svg" viewBox={`0 0 ${data.w} ${data.h}`} aria-hidden="true" focusable="false">
        <defs>
          <pattern id="storm-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(32)">
            <rect width="8" height="8" fill="rgb(56 163 232 / 16%)" />
            <line x1="4" y1="0" x2="4" y2="8" stroke="rgb(11 99 201 / 55%)" strokeWidth="1.3" />
          </pattern>
          <filter id="storm-soft" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="5" />
          </filter>
        </defs>
        <Paths data={data} />
      </svg>
      <div className="storm-map__overlay">
        <Labels data={data} />
      </div>
      <span className="storm-map__chip">
        <span className="storm-map__chip-dot" />
        {when}
      </span>
      <NorthArrow />
      <Legend />
    </figure>
  )
}
