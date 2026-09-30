/** Ward + hex GeoJSON (SPEC §19 /api/geo/*), fetched once per API instance and cached. */
import type { Api } from '../api/endpoints'
import type { MapGeo } from '../components/map/LiveMap'
import { useAsync, type AsyncState } from './useAsync'

const cache = new WeakMap<Api, Promise<MapGeo>>()

export function loadGeo(api: Api): Promise<MapGeo> {
  const cached = cache.get(api)
  if (cached) return cached
  const pending = Promise.all([api.zonesGeo(), api.hexesGeo()]).then(([zones, hexes]) => ({ zones, hexes }))
  cache.set(api, pending)
  pending.catch(() => cache.delete(api))
  return pending
}

export function useGeo(api: Api): AsyncState<MapGeo> {
  return useAsync(() => loadGeo(api), [api])
}
