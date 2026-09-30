/**
 * The storm at 17:05 as a static, non-interactive map (deck slide 6; SPEC §17.2 golden labels;
 * B3 hex values): sea and land built from the ward polygons (land without shops stippled), hexes
 * on the deck's colour scale, white ward borders, the rain band hatched above the hexes with a
 * dashed edge, Anil's zone (Z7) outlined in navy, dark zone labels on leader lines placed clear of
 * every overlay (useStormLabels), the Z9 callout, Anil's pin card and the legend. Drawn from
 * `content/stormMap.json` (see stormMapData.ts), so it needs no tiles, no Leaflet and no network.
 */
import { useRef, type CSSProperties } from 'react'

import stormMap from '../../content/stormMap.json'
import { indexColour } from '../../lib/colour'
import { Icon } from '../common/Icon'
import { Legend, MapPatternDefs, NorthArrow } from '../map/overlays'
import type { Point, StormLabel, StormMapData } from './stormMapData'
import { useStormLabels } from './useStormLabels'

export const STORM_MAP: StormMapData = stormMap as unknown as StormMapData

/** Label offsets from their zone anchor, in SVG units (deck slide 6: Z3 left, Z12 below, Z7 right). */
export const LABEL_OFFSETS: Readonly<Record<string, Point>> = Object.freeze({
  Z3: [-118, 26],
  Z7: [128, 34],
  Z12: [96, 58],
  Z9: [58, -70],
})
/** The direction each label prefers when it has to move (radians, from LABEL_OFFSETS). */
export const LABEL_PREFER: Readonly<Record<string, number>> = Object.freeze(
  Object.fromEntries(Object.entries(LABEL_OFFSETS).map(([id, [dx, dy]]) => [id, Math.atan2(dy, dx)])),
)
/** Anil's zone (B5 demo merchant S-0142): outlined in navy like the live map's selected zone. */
export const FOCUS_ZONE = 'Z7'
/** SVG pattern ids of this map (MapPatternDefs): `storm-hatch`, `storm-stipple`. */
const PATTERNS = 'storm'
/** Where the water names sit in the frame (SVG units). */
const WATER: readonly { name: string; at: Point }[] = [
  { name: 'Arabian Sea', at: [96, 548] },
  { name: 'Harbour', at: [705, 470] },
]
const RAIN_CAPTION = 'Heavy rain band · since 14:00'
const PCT = 100

type Positioned = CSSProperties & Record<`--${string}`, string>

function at(point: Point, data: StormMapData): Positioned {
  return { '--x': `${(point[0] / data.w) * PCT}%`, '--y': `${(point[1] / data.h) * PCT}%` }
}

/**
 * First-paint position of a label: the deck offset in container-width units (the frame keeps the
 * SVG's aspect ratio), with the leader line's length and angle. useStormLabels refines it.
 */
export function deckOffset(label: StormLabel, data: StormMapData): Positioned {
  const [dx, dy] = LABEL_OFFSETS[label.id] ?? [0, 0]
  const unit = (n: number) => `${(n / data.w) * PCT}cqw`
  return { ...at(label.at, data), '--dx': unit(dx), '--dy': unit(dy), '--len': unit(Math.hypot(dx, dy)), '--angle': `${Math.atan2(dy, dx)}rad` }
}

function Paths({ data }: { data: StormMapData }) {
  const rain = data.land.filter((z) => data.rain.includes(z.id))
  const focus = data.land.filter((z) => z.id === FOCUS_ZONE)
  return (
    <>
      <rect className="storm-map__sea" width={data.w} height={data.h} />
      {['shallows', 'coast', 'land'].map((layer) => (
        <g key={layer} className={`storm-map__${layer}`}>
          {data.land.map((z) => (
            <path key={z.id} d={z.d} />
          ))}
        </g>
      ))}
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
      <g className="storm-map__rain-fill">{rain.map((z) => <path key={z.id} d={z.d} fill={`url(#${PATTERNS}-hatch)`} />)}</g>
      <g className="storm-map__rain-edge">{rain.map((z) => <path key={z.id} d={z.d} />)}</g>
      {['focus-halo', 'focus'].map((layer) => (
        <g key={layer} className={`storm-map__${layer}`}>
          {focus.map((z) => (
            <path key={z.id} d={z.d} />
          ))}
        </g>
      ))}
    </>
  )
}

function Labels({ data }: { data: StormMapData }) {
  return (
    <>
      {data.labels.map((l) => (
        <div key={l.id} className="zone-anchor storm-anchor" data-label={l.id} data-moved="true" style={deckOffset(l, data)}>
          <span className="zone-anchor__line" />
          <span className="zone-anchor__dot" />
          {l.status === 'slow_day' ? (
            <div className="storm-label storm-label--slow" data-box>
              <strong>{l.text}</strong>
              <span>Slow day, no alert: no payout</span>
            </div>
          ) : (
            <div className={`storm-label storm-label--${l.status}`} data-box>
              {l.text}
            </div>
          )}
        </div>
      ))}
      {data.pin ? (
        <div className="storm-pin" style={at(data.pin.at, data)}>
          <span className="storm-pin__dot" data-obstacle />
          <div className="storm-pin__card" data-obstacle>
            <strong>{data.pin.name}</strong>
            <span>{data.pin.caption}</span>
          </div>
        </div>
      ) : null}
      {data.rainTop ? (
        <span className="rain-pill storm-map__rain-pill" style={at(data.rainTop, data)} data-obstacle>
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
  const ref = useRef<HTMLElement>(null)
  useStormLabels(ref, LABEL_PREFER)
  return (
    <figure ref={ref} className="storm-map" aria-label={`Storm replay map at ${when}`}>
      <MapPatternDefs prefix={PATTERNS} />
      <div className="storm-map__frame">
        <svg className="storm-map__svg" viewBox={`0 0 ${data.w} ${data.h}`} aria-hidden="true" focusable="false">
          <Paths data={data} />
        </svg>
        <div className="storm-map__overlay">
          <Labels data={data} />
        </div>
        <span className="storm-map__chip" data-obstacle>
          <span className="storm-map__chip-dot" />
          {when}
        </span>
        <NorthArrow />
      </div>
      {/* Over the map's corner on wide frames, a strip under the map on narrow ones (storm.css). */}
      <Legend patterns={PATTERNS} />
    </figure>
  )
}
