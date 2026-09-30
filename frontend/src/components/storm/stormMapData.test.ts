/**
 * Static storm map (deck slide 6, SPEC §17.2): projection, paths, and the committed 17:05 frame.
 * `content/stormMap.json` must equal what the mock monsoon replay produces at 17:05; after a
 * deliberate change to the replay or the geometry, regenerate it with `npx vitest run -u`.
 */
import type { FeatureCollection } from 'geojson'
import { describe, expect, it } from 'vitest'

import stormMap from '../../content/stormMap.json'
import { FOCUS_ZONES } from '../map/geo'
import { pinCaption } from '../map/LiveMap'
import { ANIL } from '../../mock/fixtures'
import { testBackend } from '../../mock/testkit'
import { merchantDetailView, snapshotView } from '../../mock/views'
import { buildStormMap, featurePath, frameProjection, STORM_VIEW, topPoint, type StormMapData } from './stormMapData'

function monsoonAt1705(): StormMapData {
  const backend = testBackend()
  try {
    backend.seek('17:05')
    const snapshot = snapshotView(backend.runtime, backend.geo)
    const anil = merchantDetailView(backend.runtime, ANIL)
    return buildStormMap({
      zones: backend.geo.zones as FeatureCollection,
      hexes: backend.geo.hexes as FeatureCollection,
      snapshot,
      focus: FOCUS_ZONES,
      pin: { lat: anil.lat, lng: anil.lng, name: anil.shop_name, caption: pinCaption(anil, '2025-08-19') },
    })
  } finally {
    backend.dispose()
  }
}

describe('projection', () => {
  it('centres the bounds in the frame and keeps north up', () => {
    const project = frameProjection([
      [18.9, 72.8],
      [19.1, 72.9],
    ])
    const [cx, cy] = project(72.85, 19.0)
    expect(cx).toBe(STORM_VIEW.w / 2)
    expect(cy).toBe(STORM_VIEW.h / 2)
    expect(project(72.85, 19.1)[1]).toBeLessThan(cy)
    expect(project(72.9, 19.0)[0]).toBeGreaterThan(cx)
  })

  it('draws polygons with holes and skips degenerate rings', () => {
    const project = frameProjection([
      [0, 0],
      [1, 1],
    ])
    const square = (d: number) => [
      [0, 0],
      [d, 0],
      [d, d],
      [0, d],
      [0, 0],
    ]
    const poly = { type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [square(1), square(0.5)] } }
    expect(featurePath(poly, project).match(/M/g)).toHaveLength(2)
    const empty = { type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [[[0, 0], [0, 0], [0, 0]]] } }
    expect(featurePath(empty, project)).toBe('')
    const point = { type: 'Feature' as const, properties: {}, geometry: { type: 'Point' as const, coordinates: [0, 0] } }
    expect(featurePath(point, project)).toBe('')
  })

  it('finds the northernmost point of a band', () => {
    const project = frameProjection([
      [0, 0],
      [1, 1],
    ])
    const ring = [
      [0, 0],
      [1, 0],
      [0.5, 1],
      [0, 0],
    ]
    const band = [{ type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [ring] } }]
    expect(topPoint(band, project)).toEqual(project(0.5, 1))
    expect(topPoint([], project)).toBeNull()
  })

  it('refuses to build without geometry for the focus zones', () => {
    const empty: FeatureCollection = { type: 'FeatureCollection', features: [] }
    const snapshot = { hexes: {}, zones: [], triggers: [], rain_band: null }
    expect(() => buildStormMap({ zones: empty, hexes: empty, snapshot, focus: ['Z7'], pin: null })).toThrow(/no ward geometry/)
  })
})

describe('monsoon replay at 17:05', () => {
  const data = monsoonAt1705()

  it('carries the SPEC §17.2 golden labels, the paid pin and the rain band', () => {
    const labels = Object.fromEntries(data.labels.map((l) => [l.id, l.text]))
    expect(labels).toEqual({ Z3: 'Z3 · 38% · 141 shops', Z7: 'Z7 · 37% · 46 shops', Z9: 'Z9 · 61% of expected', Z12: 'Z12 · 47% · 125 shops' })
    expect(data.pin?.caption).toBe('₹1,380 paid · 17:04')
    expect(data.triggered).toEqual(['Z12', 'Z3', 'Z7'])
    expect(data.rain).toEqual(['Z12', 'Z3', 'Z7'])
    expect(data.hourly.Z7).toHaveLength(3)
    expect(data.rainTop?.[1]).toBeLessThan(data.labels.find((l) => l.id === 'Z7')?.at[1] ?? 0)
    expect(data.hexes.length).toBeGreaterThan(100)
  })

  it('matches the committed content/stormMap.json', async () => {
    await expect(`${JSON.stringify(data)}\n`).toMatchFileSnapshot('../../content/stormMap.json')
    expect(stormMap).toEqual(data)
  })
})
