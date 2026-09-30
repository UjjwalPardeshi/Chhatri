/** Test helpers for the mock backend (used by *.test.ts only). */
import type { FeatureCollection } from 'geojson'

import { ApiClient } from '../api/client'
import { createApi } from '../api/endpoints'
import { MockBackend } from './backend'
import hexes from './data/hexes.json'
import zones from './data/zones.json'
import { createMockFetch } from './fetch'
import { makeGeo, zoneMetas } from './views'

export const FIXED_WALL_CLOCK = '2026-10-03T10:00:00.000Z'

export function testBackend(): MockBackend {
  const geo = makeGeo(zones as unknown as FeatureCollection, hexes as unknown as FeatureCollection)
  return new MockBackend(geo, zoneMetas(geo.zones), { wallClock: () => FIXED_WALL_CLOCK, tickMs: 50 })
}

export function testApi(backend = testBackend()) {
  const client = new ApiClient(createMockFetch(backend))
  return { backend, api: createApi(client), client }
}
