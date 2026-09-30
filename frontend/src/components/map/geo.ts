/**
 * Geo helpers for the live map (SPEC §5.1 ward polygons, §5.2 H3 hexes served as GeoJSON).
 * Label anchors use the area-weighted centroid of a zone's largest polygon ring.
 */
import type { Feature, FeatureCollection, MultiPolygon, Polygon, Position } from 'geojson'

export type LatLng = [number, number]
export type Bounds = [LatLng, LatLng]

/** Zones the deck's map frames: Z3 west on the coast, Z7 centre, Z12 south-east, Z9 by the harbour. */
export const FOCUS_ZONES: readonly string[] = ['Z3', 'Z7', 'Z9', 'Z12']
/** The storm cluster the live map is framed on (SPEC §17.2 monsoon: the three alert zones). */
export const STORM_ZONES: readonly string[] = ['Z3', 'Z7', 'Z12']
/** Zones kept in view by their label anchor only (Z9's slow-day callout, deck slide 6 top right). */
export const CONTEXT_ZONES: readonly string[] = ['Z9']

function ringArea(ring: readonly Position[]): number {
  let area = 0
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) area += ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1]
  return area / 2
}

function ringCentroid(ring: readonly Position[]): LatLng {
  const area = ringArea(ring)
  if (area === 0) return [ring[0][1], ring[0][0]]
  let cx = 0
  let cy = 0
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const cross = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1]
    cx += (ring[j][0] + ring[i][0]) * cross
    cy += (ring[j][1] + ring[i][1]) * cross
  }
  return [cy / (6 * area), cx / (6 * area)]
}

function outerRings(geometry: Polygon | MultiPolygon): Position[][] {
  return geometry.type === 'Polygon' ? [geometry.coordinates[0]] : geometry.coordinates.map((poly) => poly[0])
}

function isPolygonal(feature: Feature): feature is Feature<Polygon | MultiPolygon> {
  return feature.geometry?.type === 'Polygon' || feature.geometry?.type === 'MultiPolygon'
}

/** Label anchor of a ward: centroid of its largest outer ring. */
export function featureCentroid(feature: Feature): LatLng | null {
  if (!isPolygonal(feature)) return null
  const rings = outerRings(feature.geometry)
  const largest = rings.reduce((best, ring) => (Math.abs(ringArea(ring)) > Math.abs(ringArea(best)) ? ring : best), rings[0])
  return largest ? ringCentroid(largest) : null
}

export function zoneId(feature: Feature): string {
  return String(feature.properties?.id ?? feature.properties?.zone_id ?? '')
}

export function centroidsById(zones: FeatureCollection): ReadonlyMap<string, LatLng> {
  const out = new Map<string, LatLng>()
  for (const feature of zones.features) {
    const centre = featureCentroid(feature)
    if (centre) out.set(zoneId(feature), centre)
  }
  return out
}

/** Bounding box of the given zones (all zones when none match). */
export function boundsOf(zones: FeatureCollection, ids: readonly string[]): Bounds | null {
  const chosen = zones.features.filter((f) => ids.includes(zoneId(f)))
  const features = chosen.length > 0 ? chosen : zones.features
  let south = Infinity
  let west = Infinity
  let north = -Infinity
  let east = -Infinity
  for (const feature of features) {
    if (!isPolygonal(feature)) continue
    for (const ring of outerRings(feature.geometry)) {
      for (const [lng, lat] of ring) {
        south = Math.min(south, lat)
        north = Math.max(north, lat)
        west = Math.min(west, lng)
        east = Math.max(east, lng)
      }
    }
  }
  return Number.isFinite(south) ? [[south, west], [north, east]] : null
}

/** North-west corner of a collection (anchor for the rain band label). */
export function northWestOf(collection: FeatureCollection): LatLng | null {
  const bounds = boundsOf(collection, [])
  return bounds ? [bounds[1][0], bounds[0][1]] : null
}

/** Grows `bounds` to include `points` (label anchors that must stay on screen). */
export function extendBounds(bounds: Bounds, points: readonly LatLng[]): Bounds {
  return points.reduce<Bounds>(
    ([[south, west], [north, east]], [lat, lng]) => [
      [Math.min(south, lat), Math.min(west, lng)],
      [Math.max(north, lat), Math.max(east, lng)],
    ],
    bounds,
  )
}

/**
 * The live map's frame (deck slide 6): the storm zones fill the map, and on wide screens the
 * context zones' label anchors are added so the Z9 callout stays on the map. On a phone only the
 * storm cluster is framed; the Z9 label then clamps to the map edge as an edge callout.
 */
export function stormFrame(zones: FeatureCollection, compact: boolean): Bounds | null {
  const storm = boundsOf(zones, STORM_ZONES)
  if (!storm || compact) return storm
  const centroids = centroidsById(zones)
  const anchors = CONTEXT_ZONES.flatMap((id) => {
    const at = centroids.get(id)
    return at ? [at] : []
  })
  return extendBounds(storm, anchors)
}

/** The northernmost outer-ring vertex of a collection (where the rain band's label sits). */
export function northernmostOf(collection: FeatureCollection): LatLng | null {
  let top: LatLng | null = null
  for (const feature of collection.features) {
    if (!isPolygonal(feature)) continue
    for (const ring of outerRings(feature.geometry)) {
      for (const [lng, lat] of ring) {
        if (!top || lat > top[0]) top = [lat, lng]
      }
    }
  }
  return top
}
