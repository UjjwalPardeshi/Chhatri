/**
 * Mock mode entry (binding decision B7). Loaded lazily so the real console bundle never carries
 * the mock backend or its geo data.
 */
import type { FeatureCollection } from 'geojson'

import type { FetchLike } from '../api/client'
import { MockBackend } from './backend'
import { createMockFetch } from './fetch'
import { makeGeo, zoneMetas } from './views'

export type MockEnvironment = { backend: MockBackend; fetch: FetchLike }

export async function startMock(): Promise<MockEnvironment> {
  const [zones, hexes] = await Promise.all([import('./data/zones.json'), import('./data/hexes.json')])
  const geo = makeGeo(zones.default as unknown as FeatureCollection, hexes.default as unknown as FeatureCollection)
  const backend = new MockBackend(geo, zoneMetas(geo.zones))
  return { backend, fetch: createMockFetch(backend) }
}
