/**
 * Basemap for the live map (SPEC §20 "Live map": CARTO Positron with attribution and a graceful
 * fallback to no tiles). Without a tile key the console draws its own basemap from the ward
 * polygons: a soft sea, paper-tinted land with a shallow-water halo along the coast and a crisp
 * coastline, styled by CSS classes (tokens --sea, --land, --coast) so it matches the static map.
 */
import L from 'leaflet'
import type { FeatureCollection } from 'geojson'
import { useEffect } from 'react'
import { useMap } from 'react-leaflet'

import { probeTiles, tileTemplate, type TileProbe } from '../../lib/tiles'
import { useLatest } from '../../state/useLatest'

export const CARTO_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a> · Wards: DataMeet (CC BY-SA 2.5 India)'
export const TILE_ERROR_LIMIT = 4
export const TILE_TIMEOUT_MS = 8_000

export type TileFailure = Exclude<TileProbe, 'ok'> | 'errors'

type TileProps = { onFallback: (reason: TileFailure) => void; onLoaded: () => void }

/**
 * CARTO Positron with graceful fallback (SPEC §20): a probe tile first (watermark/offline ⇒ no
 * tiles), then repeated tile errors or no tile within the timeout ⇒ no tiles. `onLoaded` fires
 * once real tiles are on screen (the footer then credits CARTO and OpenStreetMap).
 */
export function Tiles({ onFallback, onLoaded }: TileProps) {
  const map = useMap()
  const callbacks = useLatest({ onFallback, onLoaded })
  useEffect(() => {
    let cancelled = false
    let layer: L.TileLayer | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    const fail = (reason: TileFailure) => {
      if (cancelled) return
      console.warn(`[map] basemap unavailable (${reason}); drawing the ward basemap`)
      layer?.remove()
      callbacks.current.onFallback(reason)
    }
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      fail('unreachable')
      return undefined
    }
    const template = tileTemplate(import.meta.env.VITE_TILE_URL)
    const centre = map.getCenter()
    void probeTiles(window.fetch.bind(window), template, centre.lat, centre.lng).then((result) => {
      if (cancelled) return
      if (result !== 'ok') {
        fail(result)
        return
      }
      let loaded = 0
      let failed = 0
      const tiles = L.tileLayer(template, { subdomains: 'abcd', maxZoom: 19, attribution: CARTO_ATTRIBUTION, className: 'map-tiles' })
      tiles.on('tileload', () => {
        loaded += 1
        if (loaded === 1) callbacks.current.onLoaded()
      })
      tiles.on('tileerror', () => {
        failed += 1
        if (loaded === 0 && failed === TILE_ERROR_LIMIT) fail('errors')
      })
      timer = setTimeout(() => {
        if (loaded === 0) fail('errors')
      }, TILE_TIMEOUT_MS)
      layer = tiles
      tiles.addTo(map)
    })
    return () => {
      cancelled = true
      clearTimeout(timer)
      layer?.remove()
    }
  }, [map, callbacks])
  return null
}

/** Stroke widths of the drawn basemap (px): the shallow-water halo and the coastline (half shows). */
const SHALLOWS_WEIGHT = 14
const COAST_WEIGHT = 2

/**
 * The ward basemap shown without tiles. Each ward is drawn three times: a wide soft halo, then a
 * thin coast line, then the land fill on top (a light stipple, MapPatternDefs `${patterns}-stipple`,
 * which shows wherever no shop hexes cover the land). Neighbouring land covers both strokes inside
 * the city, so only their outer halves show: shallow water and a crisp coastline along the sea.
 */
export function LandLayer({ zones, patterns }: { zones: FeatureCollection; patterns: string }) {
  const map = useMap()
  useEffect(() => {
    const layers = [
      L.geoJSON(zones, { pane: 'land', interactive: false, style: { className: 'basemap-shallows', weight: SHALLOWS_WEIGHT, fill: false, lineJoin: 'round' } }),
      L.geoJSON(zones, { pane: 'land', interactive: false, style: { className: 'basemap-coast', weight: COAST_WEIGHT, fill: false, lineJoin: 'round' } }),
      L.geoJSON(zones, { pane: 'land', interactive: false, style: { className: 'basemap-land', stroke: false, fillColor: `url(#${patterns}-stipple)`, fillOpacity: 1 } }),
    ]
    for (const layer of layers) layer.addTo(map)
    return () => {
      for (const layer of layers) layer.remove()
    }
  }, [map, zones, patterns])
  return null
}
