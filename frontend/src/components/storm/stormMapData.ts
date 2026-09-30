/**
 * Static storm map data (deck slide 6; SPEC §17.2 at 17:05; B3 hex values). Projects the ward
 * polygons, H3 hexes, rain band, zone label anchors and the demo merchant's pin of one replay
 * snapshot into a fixed 4:3 SVG frame around the storm zones, so the Overview can draw the map
 * with no Leaflet, no tiles and no network. `content/stormMap.json` is this function's output for
 * the monsoon replay at 17:05 (regenerated and checked by stormMapData.test.ts).
 */
import type { Feature, FeatureCollection, MultiPolygon, Polygon, Position } from 'geojson'

import type { StateSnapshot, ZoneStatusName } from '../../api/types'
import { boundsOf, centroidsById, zoneId, type Bounds } from '../map/geo'

export const STORM_VIEW = Object.freeze({ w: 800, h: 600 })
/** Share of the frame left around the focus zones on each side. */
const FRAME_PAD = 0.06
/** Coordinates are kept to 0.1 SVG units (sub-pixel at any display size). */
const PRECISION = 10
const DEG = Math.PI / 180
/** Hexes and wards whose box lies this far outside the frame are dropped. */
const CULL_MARGIN = 40
const LABELLED: ReadonlySet<ZoneStatusName> = new Set(['triggered', 'slow_day'])

export type Point = readonly [number, number]
export type StormLabel = { id: string; at: Point; text: string; status: ZoneStatusName }
export type StormPin = { at: Point; name: string; caption: string }
export type StormMapData = {
  w: number
  h: number
  land: readonly { id: string; d: string }[]
  hexes: readonly { d: string; v: number | null }[]
  triggered: readonly string[]
  rain: readonly string[]
  labels: readonly StormLabel[]
  pin: StormPin | null
  /** Northernmost point of the rain band (where its label sits), null without rain. */
  rainTop: Point | null
  hourly: Readonly<Record<string, readonly number[]>>
}

export type StormInput = {
  zones: FeatureCollection
  hexes: FeatureCollection
  snapshot: Pick<StateSnapshot, 'hexes' | 'zones' | 'triggers' | 'rain_band'>
  focus: readonly string[]
  pin: { lat: number; lng: number; name: string; caption: string } | null
}

type Projection = (lng: number, lat: number) => Point

const round = (n: number): number => Math.round(n * PRECISION) / PRECISION

/** Equirectangular projection (cos-latitude corrected) of `bounds` padded to the frame's aspect. */
export function frameProjection(bounds: Bounds, view: { w: number; h: number } = STORM_VIEW): Projection {
  const [[south, west], [north, east]] = bounds
  const kx = Math.cos(((south + north) / 2) * DEG)
  const spanX = (east - west) * kx
  const spanY = north - south
  const aspect = view.w / view.h
  const paddedX = Math.max(spanX, spanY * aspect) * (1 + 2 * FRAME_PAD)
  const scale = view.w / paddedX
  const cx = ((west + east) / 2) * kx
  const cy = (south + north) / 2
  return (lng, lat) => [round((lng * kx - cx) * scale + view.w / 2), round((cy - lat) * scale + view.h / 2)]
}

function ringPath(ring: readonly Position[], project: Projection): string {
  const points: Point[] = []
  for (const [lng, lat] of ring) {
    const p = project(lng, lat)
    const last = points.at(-1)
    if (!last || last[0] !== p[0] || last[1] !== p[1]) points.push(p)
  }
  return points.length < 3 ? '' : `M${points.map(([x, y]) => `${x} ${y}`).join('L')}Z`
}

function polygons(feature: Feature): Position[][][] {
  const geometry = feature.geometry as Polygon | MultiPolygon | null
  if (geometry?.type === 'Polygon') return [geometry.coordinates]
  if (geometry?.type === 'MultiPolygon') return geometry.coordinates
  return []
}

/** SVG path of a (multi)polygon, holes included (render with fill-rule evenodd). */
export function featurePath(feature: Feature, project: Projection): string {
  return polygons(feature)
    .flatMap((poly) => poly.map((ring) => ringPath(ring, project)))
    .filter((d) => d !== '')
    .join('')
}

function inFrame(feature: Feature, project: Projection, view: { w: number; h: number }): boolean {
  return polygons(feature).some((poly) =>
    poly[0]?.some(([lng, lat]) => {
      const [x, y] = project(lng, lat)
      return x > -CULL_MARGIN && x < view.w + CULL_MARGIN && y > -CULL_MARGIN && y < view.h + CULL_MARGIN
    }),
  )
}

/** The northernmost projected vertex of the rain band (smallest y), or null without rain. */
export function topPoint(features: readonly Feature[], project: Projection): Point | null {
  let top: Point | null = null
  for (const feature of features) {
    for (const poly of polygons(feature)) {
      for (const [lng, lat] of poly[0] ?? []) {
        const p = project(lng, lat)
        if (!top || p[1] < top[1]) top = p
      }
    }
  }
  return top
}

function zoneLabels(input: StormInput, project: Projection): StormLabel[] {
  const centroids = centroidsById(input.zones)
  return input.snapshot.zones.flatMap((zone) => {
    const centre = centroids.get(zone.zone_id)
    if (!centre || !LABELLED.has(zone.status)) return []
    /** B3: labels read the trailing 3-hour index, like the Z9 explanation. */
    const text = zone.status === 'slow_day' ? `${zone.zone_id} · ${zone.index_pct ?? '—'}% of expected` : zone.label
    return [{ id: zone.zone_id, at: project(centre[1], centre[0]), text, status: zone.status }]
  })
}

export function buildStormMap(input: StormInput, view: { w: number; h: number } = STORM_VIEW): StormMapData {
  const bounds = boundsOf(input.zones, input.focus)
  if (!bounds) throw new Error('buildStormMap: no ward geometry for the focus zones')
  const project = frameProjection(bounds, view)
  const land = input.zones.features.filter((f) => inFrame(f, project, view)).map((f) => ({ id: zoneId(f), d: featurePath(f, project) }))
  const hexes = input.hexes.features
    .filter((f) => inFrame(f, project, view))
    .map((f) => ({ d: featurePath(f, project), v: input.snapshot.hexes[String(f.properties?.h3)] ?? null }))
  const bandFeatures = input.snapshot.rain_band?.features ?? []
  const rain = bandFeatures.map((f) => zoneId(f)).toSorted()
  const hourly = Object.fromEntries(input.snapshot.triggers.map((t) => [t.zone_id, t.hourly_index_pct]))
  return {
    w: view.w,
    h: view.h,
    land,
    hexes,
    triggered: input.snapshot.triggers.map((t) => t.zone_id).toSorted(),
    rain,
    labels: zoneLabels(input, project),
    pin: input.pin ? { at: project(input.pin.lng, input.pin.lat), name: input.pin.name, caption: input.pin.caption } : null,
    rainTop: topPoint(bandFeatures, project),
    hourly,
  }
}
